"""API configuration and translation services.

This module encapsulates all logic related to managing API keys and
performing translations or other language tasks. Functions here are
extracted from the original main module to keep that file focused on
UI logic. Import this module to access translation functions such as
``translate_text``, ``translate_baidu``, ``translate_zhipu`` and
``translate_zhipu_glm45``. It also exposes helper functions to load
and save API configurations stored in ``apis.json``.
"""

from __future__ import annotations

import os
import json
import time
import random
import hashlib
from typing import Tuple, Dict, Any, Optional

import requests

from .file_utils import safe_json_load, safe_json_save
from .logger import logger, handle_api_error, safe_execute

try:
    from tkinter import messagebox
except ImportError:
    messagebox = None

def has_available_translation_credentials() -> bool:
    """Check if there are available translation credentials for any platform."""
    for platform in ["baidu", "zhipu", "zhipu-glm45"]:
        apis = api_config.get(platform, [])
        if any(not api.get("disabled", False) for api in apis):
            return True
    return False

def prompt_for_translation_credentials() -> str:
    """Prompt user to configure translation credentials."""
    message = "未配置翻译API凭据，请在设置中配置后重试。"
    if messagebox:
        messagebox.showwarning("缺少API凭据", message)
    return f"[{message}]"

def set_current_platform(platform: str) -> None:
    """Set the current translation platform."""
    global current_platform
    if platform in ["baidu", "zhipu", "zhipu-glm45"]:
        current_platform = platform
        # 保存用户的平台选择
        try:
            from views.ui_main import save_config, load_config
            config = load_config()
            config['current_platform'] = platform
            save_config(config)
        except Exception as e:
            logger.warning(f"Failed to save platform config: {e}")
    else:
        logger.warning(f"Unknown platform: {platform}")

def get_current_platform() -> str:
    """Get the current translation platform."""
    return current_platform

# Configuration file storing API credentials. Relative to project root.
API_CONFIG_FILE: str = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "apis.json")

# In-memory configuration loaded from the JSON file. Keys are platform
# names (e.g. "baidu", "zhipu", "zhipu-glm45"). Values are lists of
# credential dicts. The structure of each dict depends on the platform.
api_config: Dict[str, list] = {}

# Index of the currently selected API account for each platform. Used to
# cycle through available credentials when one fails.
current_api_index: Dict[str, int] = {}

# Currently selected platform for translation. This can be modified
# externally to switch between different providers.
current_platform: str = "baidu"

def load_api_config() -> None:
    """Load API configuration from disk into ``api_config``.

    If the file does not exist, a default structure with empty lists
    for each supported platform is created. ``current_api_index`` is
    reset to zero for each platform.
    """
    global api_config, current_api_index, current_platform
    default_config = {"baidu": [], "zhipu": [], "zhipu-glm45": []}
    api_config = safe_json_load(API_CONFIG_FILE, default_config)
    # Ensure new platforms exist
    api_config.setdefault("zhipu-glm45", [])
    # Reset current index per platform
    for plat in api_config:
        current_api_index[plat] = 0
    
    # 加载用户保存的平台选择
    try:
        from views.ui_main import load_config
        config = load_config()
        saved_platform = config.get('current_platform', 'baidu')
        current_platform = saved_platform
    except Exception as e:
        logger.warning(f"Failed to load platform config: {e}")

def save_api_config() -> None:
    """Persist the current API configuration to disk."""
    safe_json_save(API_CONFIG_FILE, api_config)

def get_next_api_info(platform: str) -> Tuple[Optional[Dict[str, Any]], Optional[int]]:
    """Return the next available API account for a given platform.

    Accounts marked as ``disabled`` are skipped. ``current_api_index``
    tracks where the search should resume next time. If no usable
    account is found, ``(None, None)`` is returned.
    """
    apis = api_config.get(platform, [])
    n = len(apis)
    for i in range(n):
        idx = (current_api_index.get(platform, 0) + i) % n
        if not apis[idx].get("disabled", False):
            current_api_index[platform] = idx
            return apis[idx], idx
    return None, None

def mark_api_disabled(platform: str, idx: int) -> None:
    """Mark an API account as disabled and persist the change."""
    if 0 <= idx < len(api_config.get(platform, [])):
        api_config[platform][idx]["disabled"] = True
        save_api_config()

def contains_chinese(text: str) -> bool:
    """Return True if the given text contains any Chinese characters."""
    return any('\u4e00' <= ch <= '\u9fff' for ch in text)

def translate_text(text: str) -> str:
    """Translate text using the currently selected platform.

    Delegates to the appropriate platform-specific translation
    function. If an error occurs during translation, a human-friendly
    message is returned instead of raising an exception.
    """
    global current_platform
    
    # 检查是否有可用的API凭据
    if not has_available_translation_credentials():
        return prompt_for_translation_credentials()
    
    def _translate():
        if current_platform == "baidu":
            return translate_baidu(text)
        elif current_platform == "zhipu":
            return translate_zhipu(text)
        elif current_platform == "zhipu-glm45":
            return translate_zhipu_glm45(text)
        else:
            logger.warning(f"Unknown platform: {current_platform}")
            return "[未实现平台]"
    
    result = safe_execute(_translate, default_return=f"翻译失败: 未知错误")
    return result if result is not None else f"翻译失败: 未知错误"

def translate_baidu(text: str) -> str:
    """Translate using Baidu Fanyi API.

    Handles account cycling and error handling. If all configured
    accounts are disabled or unusable, returns a human-readable message.
    """
    def _baidu_translate():
        apis = api_config.get("baidu", [])
        tries = len(apis)
        for _ in range(tries):
            api, idx = get_next_api_info("baidu")
            if not api:
                logger.warning("No available Baidu API accounts")
                return "[本平台无可用百度API账号]"
            appid = api.get("app_id")
            key = api.get("app_key")
            salt = random.randint(32768, 65536)
            q = text
            # 固定英译中方向
            from_lang = 'en'
            to_lang = 'zh'
            sign = hashlib.md5((appid + q + str(salt) + key).encode()).hexdigest()
            url = "https://fanyi-api.baidu.com/api/trans/vip/translate"
            params = {
                "q": q,
                "from": from_lang,
                "to": to_lang,
                "appid": appid,
                "salt": salt,
                "sign": sign,
            }
            try:
                res = requests.get(url, params=params, timeout=5).json()
                if 'trans_result' in res:
                    return res['trans_result'][0]['dst']
                elif 'error_code' in res and res['error_code'] in ['54003', '54004', '54005']:
                    logger.warning(f"Baidu API account disabled due to error: {res['error_code']}")
                    mark_api_disabled("baidu", idx)
                    continue
                else:
                    logger.error(f"Baidu API error: {res.get('error_msg', res)}")
                    return f"[翻译失败] {res.get('error_msg', res)}"
            except Exception as e:
                logger.error(f"Baidu API request failed: {str(e)}")
                mark_api_disabled("baidu", idx)
                continue
        return "[本平台无可用百度API账号]"
    
    return safe_execute(_baidu_translate, default_return="[百度翻译异常: 未知错误]")

def translate_zhipu(text: str) -> str:
    """Translate using Zhipu open API with the GLM-4-Flash model."""
    def _zhipu_translate():
        # 仅英译中：如果包含中文，直接原样返回
        if contains_chinese(text):
            return text
        apis = api_config.get("zhipu", [])
        tries = len(apis)
        for _ in range(tries):
            api, idx = get_next_api_info("zhipu")
            if not api:
                logger.warning("No available Zhipu API accounts")
                return "[本平台无可用智谱API账号]"
            api_key = api.get("api_key")
            url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
            headers = {"Authorization": f"Bearer {api_key}"}
            payload = {
                "model": "glm-4-flash",
                "messages": [
                    {"role": "system", "content": "请将用户提供的英文内容翻译成自然流畅的中文。只输出译文，不要任何额外说明。若输入不是英文，请原样输出。"},
                    {"role": "user", "content": text},
                ],
            }
            try:
                res = requests.post(url, headers=headers, json=payload, timeout=15)
                result = res.json()
                if "choices" in result and result["choices"]:
                    return result["choices"][0]["message"]["content"].strip()
                elif 'code' in result and str(result['code']) in ['100004', '100005']:
                    logger.warning(f"Zhipu API account disabled due to error: {result['code']}")
                    mark_api_disabled("zhipu", idx)
                    continue
                else:
                    logger.error(f"Zhipu API error: {result.get('message', result)}")
                    return f"[翻译失败] {result.get('message', result)}"
            except Exception as e:
                logger.error(f"Zhipu API request failed: {str(e)}")
                mark_api_disabled("zhipu", idx)
                continue
        return "[本平台无可用智谱API账号]"
    
    return safe_execute(_zhipu_translate, default_return="[智谱翻译异常: 未知错误]")

def translate_zhipu_glm45(text: str) -> str:
    """Translate using Zhipu's GLM-4.5 model."""
    def _zhipu_glm45_translate():
        # 仅英译中：如果包含中文，直接原样返回
        if contains_chinese(text):
            return text
        apis = api_config.get("zhipu-glm45", [])
        tries = len(apis)
        for _ in range(tries):
            api, idx = get_next_api_info("zhipu-glm45")
            if not api:
                logger.warning("No available Zhipu GLM-4.5 API accounts")
                return "[本平台无可用GLM-4.5 API账号]"
            api_key = api.get("api_key")
            url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
            headers = {"Authorization": f"Bearer {api_key}"}
            payload = {
                "model": "glm-4.5-longtext",
                "messages": [
                    {"role": "system", "content": "请将用户提供的英文内容翻译成自然流畅的中文。只输出译文，不要任何额外说明。若输入不是英文，请原样输出。"},
                    {"role": "user", "content": text},
                ],
            }
            try:
                res = requests.post(url, headers=headers, json=payload, timeout=20)
                result = res.json()
                if "choices" in result and result["choices"]:
                    return result["choices"][0]["message"]["content"].strip()
                elif 'code' in result and str(result['code']) in ['100004', '100005']:
                    logger.warning(f"Zhipu GLM-4.5 API account disabled due to error: {result['code']}")
                    mark_api_disabled("zhipu-glm45", idx)
                    continue
                else:
                    logger.error(f"Zhipu GLM-4.5 API error: {result.get('message', result)}")
                    return f"[翻译失败] {result.get('message', result)}"
            except Exception as e:
                logger.error(f"Zhipu GLM-4.5 API request failed: {str(e)}")
                mark_api_disabled("zhipu-glm45", idx)
                continue
        return "[本平台无可用GLM-4.5 API账号]"
    
    return safe_execute(_zhipu_glm45_translate, default_return="[智谱GLM-4.5翻译异常: 未知错误]")

def zhipu_image_caption(image_path: str) -> str:
    """Generate a caption for an image using Zhipu's GLM-4V-Flash model."""
    import base64
    from PIL import Image
    import io
    
    apis = api_config.get("zhipu", [])
    tries = len(apis)
    for _ in range(tries):
        api, idx = get_next_api_info("zhipu")
        if not api:
            return "[本平台无可用智谱API账号]"
        api_key = api.get("api_key")
        url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}"}
        
        # 读取并压缩图片，然后转换为base64编码
        try:
            # 打开图片并进行压缩处理
            with Image.open(image_path) as img:
                # 转换为RGB模式（如果是RGBA或其他模式）
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # 限制图片最大尺寸为1024x1024，保持宽高比
                max_size = 1024
                if img.width > max_size or img.height > max_size:
                    img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
                
                # 将图片保存到内存中的字节流，使用JPEG格式压缩
                img_buffer = io.BytesIO()
                img.save(img_buffer, format='JPEG', quality=85, optimize=True)
                img_buffer.seek(0)
                
                # 转换为base64编码
                img_base64 = base64.b64encode(img_buffer.getvalue()).decode('utf-8')
                
        except Exception as e:
            return f"[反推失败] 无法读取或处理图片文件: {str(e)}"
        
        payload = {
            "model": "glm-4v-flash",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "请详细描述这张图片的内容，包括物体、场景、人物、颜色等细节。"
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{img_base64}"
                            }
                        }
                    ]
                }
            ],
        }
        
        try:
            res = requests.post(url, headers=headers, json=payload, timeout=30)
            result = res.json()
            if "choices" in result and result["choices"]:
                return result["choices"][0]["message"]["content"].strip()
            elif 'code' in result and str(result['code']) in ['100004', '100005']:
                mark_api_disabled("zhipu", idx)
                continue
            else:
                return f"[反推失败] {result.get('message', result)}"
        except Exception as e:
            logger.error(f"Zhipu image caption request failed: {str(e)}")
            mark_api_disabled("zhipu", idx)
            continue
    return "[本平台无可用智谱API账号]"

def zhipu_text_expand(text: str, preset: str) -> str:
    """Expand text using Zhipu's chat API with a preset prompt."""
    apis = api_config.get("zhipu", [])
    tries = len(apis)
    for _ in range(tries):
        api, idx = get_next_api_info("zhipu")
        if not api:
            return "[本平台无可用智谱API账号]"
        api_key = api.get("api_key")
        url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}"}
        payload = {
            "model": "glm-4-flash",
            "messages": [
                {"role": "system", "content": preset},
                {"role": "user", "content": text},
            ],
        }
        try:
            res = requests.post(url, headers=headers, json=payload, timeout=20)
            result = res.json()
            if "choices" in result and result["choices"]:
                return result["choices"][0]["message"]["content"].strip()
            elif 'code' in result and str(result['code']) in ['100004', '100005']:
                mark_api_disabled("zhipu", idx)
                continue
            else:
                return f"[扩写失败] {result.get('message', result)}"
        except Exception:
            mark_api_disabled("zhipu", idx)
            continue
    return "[本平台无可用智谱API账号]"