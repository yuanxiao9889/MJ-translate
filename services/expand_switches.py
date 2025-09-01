from typing import Dict, Optional, List

# 默认选项（供 UI 组合框使用，可按需扩展）
OPTIONS: Dict[str, List[str]] = {
    "posture": ["站立", "坐姿", "行走", "奔跑", "半身", "特写"],
    "age": ["儿童", "少年", "青年", "中年", "老年"],
    "lighting": ["自然光", "逆光", "侧光", "顶光", "柔光", "硬光", "霓虹光"],
    "light_type": ["日光", "钨丝灯", "LED", "霓虹", "烛光", "闪光灯"],
    "camera_angle": ["平视", "俯拍", "仰拍", "侧拍", "45°"],
    "params": ["ISO 100, f/2.8, 1/125s"],
    "aesthetic_quality": ["标准", "高", "极高"],
    "composition_style": ["三分法", "居中", "对称", "对角线", "留白"],
    "dof": ["浅景深", "中等景深", "深景深"],
    "lens_type": ["广角(24mm)", "标准(50mm)", "长焦(85mm)", "超长焦(200mm)", "微距", "鱼眼"],
    "eye_level": ["平视", "仰视", "俯视", "低机位", "高机位"],
}

# 简单的中英映射，保证英文提示自然（覆盖常见值；未覆盖值将原样保留）
_ZH2EN_VALUE = {
    # 姿态
    "站立": "standing", "坐姿": "sitting", "行走": "walking", "奔跑": "running",
    "半身": "half-length", "特写": "close-up",
    # 年龄
    "儿童": "child", "少年": "teen", "青年": "young adult", "中年": "middle-aged", "老年": "elderly",
    # 光照/光源
    "自然光": "natural light", "逆光": "backlighting", "侧光": "sidelight", "顶光": "top light",
    "柔光": "soft light", "硬光": "hard light", "霓虹光": "neon light",
    "日光": "daylight", "钨丝灯": "tungsten", "LED": "LED", "霓虹": "neon", "烛光": "candlelight", "闪光灯": "flash",
    # 相机角度
    "平视": "eye level", "俯拍": "bird's-eye", "仰拍": "low angle", "侧拍": "side angle",
    # 构图/景深/质量
    "三分法": "rule of thirds", "居中": "centered", "对称": "symmetric", "对角线": "diagonal", "留白": "negative space",
    "浅景深": "shallow depth of field", "中等景深": "medium depth of field", "深景深": "deep depth of field",
    "标准": "standard", "高": "high", "极高": "very high",
    # 镜头/视角
    "广角(24mm)": "wide-angle (24mm)", "标准(50mm)": "standard (50mm)", "长焦(85mm)": "telephoto (85mm)",
    "超长焦(200mm)": "super telephoto (200mm)", "微距": "macro", "鱼眼": "fisheye",
    "仰视": "looking up", "俯视": "looking down", "低机位": "low viewpoint", "高机位": "high viewpoint",
}


def _kv(k_zh: str, v: Optional[str], lang: str, k_en: str) -> Optional[str]:
    if not v:
        return None
    if lang == "English":
        v_en = _ZH2EN_VALUE.get(v, v)
        return f"{k_en}: {v_en}"
    return f"{k_zh}：{v}"


def build_hints(selected: Dict[str, Dict[str, Optional[str]]], lang: str) -> str:
    """将选中的开关与取值组合成自然语言提示。

    selected 结构示例：
    {
      "person": {"posture": "站立", "age": "青年"},
      "tech": {"lighting": "自然光", "light_type": "LED", "camera_angle": "俯拍", "params": "ISO 100"},
      "composition": {"aesthetic_quality": "高", "composition_style": "三分法", "dof": "浅景深"},
      "pov": {"lens_type": "标准(50mm)", "eye_level": "平视"}
    }
    """
    parts: List[str] = []

    # 人物类
    person = selected.get("person", {})
    person_bits: List[str] = []
    person_bits.append(_kv("人物姿态", person.get("posture"), lang, "posture"))
    person_bits.append(_kv("年龄", person.get("age"), lang, "age"))
    person_bits = [p for p in person_bits if p]
    if person_bits:
        parts.append("；".join(person_bits) if lang != "English" else ", ".join(person_bits))

    # 技术信息类
    tech = selected.get("tech", {})
    tech_bits: List[str] = []
    tech_bits.append(_kv("光照", tech.get("lighting"), lang, "lighting"))
    tech_bits.append(_kv("光源类型", tech.get("light_type"), lang, "light source"))
    tech_bits.append(_kv("相机角度", tech.get("camera_angle"), lang, "camera angle"))
    if tech.get("params"):
        tech_bits.append((f"详细参数：{tech['params']}") if lang != "English" else (f"parameters: {tech['params']}"))
    tech_bits = [t for t in tech_bits if t]
    if tech_bits:
        parts.append("；".join(tech_bits) if lang != "English" else ", ".join(tech_bits))

    # 视觉构图类
    comp = selected.get("composition", {})
    comp_bits: List[str] = []
    comp_bits.append(_kv("美学质量", comp.get("aesthetic_quality"), lang, "aesthetic quality"))
    comp_bits.append(_kv("构图风格", comp.get("composition_style"), lang, "composition"))
    comp_bits.append(_kv("景深", comp.get("dof"), lang, "depth of field"))
    comp_bits = [c for c in comp_bits if c]
    if comp_bits:
        parts.append("；".join(comp_bits) if lang != "English" else ", ".join(comp_bits))

    # 视角控制类
    pov = selected.get("pov", {})
    pov_bits: List[str] = []
    pov_bits.append(_kv("镜头类型", pov.get("lens_type"), lang, "lens"))
    pov_bits.append(_kv("视角高度", pov.get("eye_level"), lang, "viewpoint"))
    pov_bits = [p for p in pov_bits if p]
    if pov_bits:
        parts.append("；".join(pov_bits) if lang != "English" else ", ".join(pov_bits))

    if not parts:
        return ""

    # 合并为 1-2 句，避免累赘
    if lang == "English":
        return ". ".join(parts) + "."
    return "。".join(parts) + "。"