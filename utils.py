import os
import json
import hashlib
from tkinter import messagebox
from oss_sync import REMOTE_JSON, LOCAL_JSON, get_oss_bucket, prompt_for_oss_credentials

def get_file_md5(path):
    import hashlib
    if not os.path.exists(path):
        return ""
    with open(path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()

def get_oss_file_md5(bucket, key):
    try:
        head = bucket.head_object(key)
        return head.etag
    except Exception:
        return ""

def get_tags_json_info(file_path):
    if not os.path.exists(file_path):
        return None, 0
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        lm = data.get("last_modified", 0)
    return data, lm

def get_oss_tags_json_info():
    try:
        bucket = get_oss_bucket()
        if bucket is None:
            return None, 0
        res = bucket.get_object(REMOTE_JSON)
        data = json.loads(res.read().decode("utf-8"))
        lm = data.get("last_modified", 0)
        return data, lm
    except Exception:
        return None, 0

def smart_sync_tags():
    """
    智能双向同步本地与云端tags.json（含冲突检测，可一键选择覆盖方向）
    """
    # 检查OSS凭据
    bucket = get_oss_bucket()
    if bucket is None:
        messagebox.showwarning("同步失败", "未配置阿里云OSS凭据，请先在设置中配置OSS凭据后重试。")
        prompt_for_oss_credentials()
        return
    
    local_data, local_lm = get_tags_json_info(LOCAL_JSON)
    oss_data, oss_lm = get_oss_tags_json_info()

    if not local_data and not oss_data:
        messagebox.showwarning("同步", "本地和云端都没有tags.json，无需同步！")
        return
    elif not local_data:
        # 本地没文件，云端有，下载覆盖
        with open(LOCAL_JSON, "w", encoding="utf-8") as f:
            json.dump(oss_data, f, ensure_ascii=False, indent=2)
        messagebox.showinfo("同步", "已用云端标签覆盖本地。")
    elif not oss_data:
        # 云端没文件，本地有，上传
        from oss_sync import upload_all
        upload_all()
        messagebox.showinfo("同步", "云端标签已更新（云端原本无数据）。")
    else:
        # 两边都有文件，比较last_modified
        if local_lm > oss_lm:
            # 本地新，自动上传
            from oss_sync import upload_all
            upload_all()
            messagebox.showinfo("同步", "本地标签较新，已上传覆盖云端。")
        elif oss_lm > local_lm:
            # 云端新，自动下载
            with open(LOCAL_JSON, "w", encoding="utf-8") as f:
                json.dump(oss_data, f, ensure_ascii=False, indent=2)
            messagebox.showinfo("同步", "云端标签较新，已覆盖本地。")
        else:
            # 时间戳相同，内容比对
            if get_file_md5(LOCAL_JSON) == get_oss_file_md5(bucket, REMOTE_JSON):
                messagebox.showinfo("同步", "本地与云端标签完全一致，无需操作。")
            else:
                # 时间戳一致但内容有变动，弹窗选择覆盖方向
                answer = messagebox.askquestion(
                    "冲突",
                    "检测到本地和云端同时被修改！\n\n选择'是'将用本地覆盖云端，\n选择'否'将用云端覆盖本地。",
                    icon='warning'
                )
                if answer == "yes":
                    from oss_sync import upload_all
                    upload_all()
                    messagebox.showinfo("同步", "已用本地内容覆盖云端。")
                else:
                    oss_data, _ = get_oss_tags_json_info()
                    with open(LOCAL_JSON, "w", encoding="utf-8") as f:
                        json.dump(oss_data, f, ensure_ascii=False, indent=2)
                    messagebox.showinfo("同步", "已用云端内容覆盖本地。")

