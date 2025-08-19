import os
import json
import hashlib
import oss2
from PIL import Image
import io
from typing import Optional, Tuple

# 导入凭据管理器
from services.credentials_manager import CredentialsManager
from services.logger import logger

try:
    from tkinter import messagebox
except ImportError:
    messagebox = None

LOCAL_JSON = "tags.json"
REMOTE_JSON = "tags.json"
LOCAL_IMG_DIR = "images"
REMOTE_IMG_PREFIX = "images/"

# 新增：收藏夹和历史记录文件配置
FAVORITES_FILE = "favorites.txt"
REMOTE_FAVORITES_FILE = "favorites.txt"
HISTORY_FILE = "history.json"
REMOTE_HISTORY_FILE = "history.json"

# 全局变量
_bucket = None
_cred_manager = None

def get_oss_credentials() -> Optional[Tuple[str, str, str, str]]:
    """获取OSS凭据
    
    Returns:
        (access_key_id, access_key_secret, endpoint, bucket_name) 或 None
    """
    global _cred_manager
    if _cred_manager is None:
        _cred_manager = CredentialsManager()
    
    # 获取启用的OSS凭据
    credentials = _cred_manager.get_credentials()
    oss_creds = credentials.get("aliyun_oss", [])
    
    # 查找第一个启用的凭据
    for cred in oss_creds:
        if not cred.get("disabled", False):
            access_key_id = cred.get("access_key_id")
            access_key_secret = cred.get("access_key_secret")
            region = cred.get("region", "oss-cn-shenzhen.aliyuncs.com")
            bucket_name = cred.get("bucket_name")
            
            if access_key_id and access_key_secret and bucket_name:
                # 确保endpoint格式正确
                if not region.startswith("https://"):
                    endpoint = f"https://{region}"
                else:
                    endpoint = region
                return access_key_id, access_key_secret, endpoint, bucket_name
    
    return None

def get_oss_bucket():
    """获取OSS bucket对象
    
    Returns:
        oss2.Bucket对象或None
    """
    global _bucket
    
    # 如果已经有bucket对象，直接返回
    if _bucket is not None:
        return _bucket
    
    # 获取凭据
    cred_info = get_oss_credentials()
    if cred_info is None:
        return None
    
    access_key_id, access_key_secret, endpoint, bucket_name = cred_info
    
    try:
        auth = oss2.Auth(access_key_id, access_key_secret)
        _bucket = oss2.Bucket(auth, endpoint, bucket_name)
        return _bucket
    except Exception as e:
        logger.error(f"创建OSS bucket失败: {e}")
        return None

def prompt_for_oss_credentials():
    """提示用户提供OSS凭据"""
    if messagebox:
        result = messagebox.askyesno(
            "缺少OSS凭据",
            "没有找到可用的阿里云OSS凭据。\n\n是否要打开凭据管理窗口添加OSS凭据？"
        )
        if result:
            # 这里可以触发打开凭据管理窗口的逻辑
            # 由于循环导入问题，这里只是提示
            messagebox.showinfo(
                "提示",
                "请通过主界面的'设置' -> 'API与存储管理'菜单添加阿里云OSS凭据。"
            )
    else:
        print("错误：没有找到可用的阿里云OSS凭据，请通过凭据管理功能添加。")

# 为了向后兼容，保留bucket变量
bucket = None

# 工具函数
def md5_of_file(path):
    with open(path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()

def md5_of_bytes(data):
    return hashlib.md5(data).hexdigest()

# ========== 上传部分 ==========
def upload_all(status_var=None, root=None):
    # 获取OSS bucket
    bucket = get_oss_bucket()
    if bucket is None:
        print("错误：无法获取OSS凭据，请先配置阿里云OSS凭据")
        prompt_for_oss_credentials()
        if status_var: status_var.set("OSS凭据未配置")
        return False
    
    files_to_upload = [
        (LOCAL_JSON, REMOTE_JSON, "tags.json"),
        (FAVORITES_FILE, REMOTE_FAVORITES_FILE, "收藏夹"),
        (HISTORY_FILE, REMOTE_HISTORY_FILE, "历史记录")
    ]
    
    total_files = len([f for f, _, _ in files_to_upload if os.path.exists(f)])
    current_file = 0
    
    for local_file, remote_file, display_name in files_to_upload:
        if not os.path.exists(local_file):
            print(f"⚠️ 本地{display_name}文件不存在，跳过")
            continue
            
        current_file += 1
        
        # JSON文件格式校验
        if local_file.endswith('.json'):
            try:
                with open(local_file, 'r', encoding='utf-8') as f:
                    json.load(f)
                print(f"✅ 本地{display_name}校验通过，准备上传")
            except Exception as e:
                print(f"❌ 本地{display_name}格式错误，上传中止！", e)
                if status_var: status_var.set(f"{display_name}格式错误，上传中止")
                return False
        
        def progress_callback(consumed_bytes, total_bytes, name=display_name, file_idx=current_file, total=total_files):
            percent = int(100 * consumed_bytes / total_bytes) if total_bytes > 0 else 100
            if status_var:
                status_var.set(f"{name}({file_idx}/{total}) 上传中 {percent}%")
            if root:
                root.update_idletasks()
        
        try:
            bucket.put_object_from_file(remote_file, local_file, progress_callback=progress_callback)
            print(f"✅ 已上传{display_name}")
            if status_var: status_var.set(f"{display_name}上传完成")
        except Exception as e:
            print(f"❌ 上传{display_name}失败：", e)
            if status_var: status_var.set(f"{display_name}上传失败")
            return False

    # 上传图片（原有逻辑）
    uploaded_keys = set()
    if os.path.isdir(LOCAL_IMG_DIR):
        img_files = [f for f in os.listdir(LOCAL_IMG_DIR) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp'))]
        total = len(img_files)
        for idx, filename in enumerate(img_files):
            local_path = os.path.join(LOCAL_IMG_DIR, filename)
            try:
                with open(local_path, "rb") as f:
                    img_bytes = f.read()
                Image.open(io.BytesIO(img_bytes)).verify()
            except Exception as e:
                print(f"⚠️ 跳过坏图片：{filename}，错误：{e}")
                continue
            remote_key = REMOTE_IMG_PREFIX + filename
            uploaded_keys.add(remote_key)
            # 增量检查
            try:
                head = bucket.head_object(remote_key)
                cloud_md5 = head.etag
                local_md5 = md5_of_bytes(img_bytes)
                if cloud_md5 == local_md5:
                    continue
            except oss2.exceptions.NoSuchKey:
                pass
            def img_progress(consumed_bytes, total_bytes, idx=idx, total=total, filename=filename):
                percent = int(100 * consumed_bytes / total_bytes)
                if status_var:
                    status_var.set(f"图片({idx+1}/{total}) {filename} 上传中 {percent}%")
                if root:
                    root.update_idletasks()
            bucket.put_object(remote_key, img_bytes, progress_callback=img_progress)
            print(f"✅ 已上传图片：{filename}")
        if status_var: status_var.set("图片上传完成")

    # 删除多余图片
    server_objs = [obj.key for obj in oss2.ObjectIterator(bucket, prefix=REMOTE_IMG_PREFIX)]
    deleted = 0
    for key in server_objs:
        if key not in uploaded_keys and key != REMOTE_IMG_PREFIX:
            bucket.delete_object(key)
            print(f"🗑️ 已删除云端多余图片：{key}")
            deleted += 1
    if deleted > 0:
        print(f"✅ 同步删除{deleted}个云端多余图片")

# ========== 下载部分 ==========
def download_all_simple():
    """下载OSS上的所有文件到本地（简单版本）"""
    print("开始从OSS下载所有文件...")
    
    # 获取OSS bucket
    bucket = get_oss_bucket()
    if bucket is None:
        print("错误：无法获取OSS凭据，请先配置阿里云OSS凭据")
        prompt_for_oss_credentials()
        return False
    
    # 1. 下载 tags.json
    try:
        bucket.get_object_to_file(REMOTE_JSON, LOCAL_JSON)
        print(f"✓ 下载 {REMOTE_JSON} -> {LOCAL_JSON}")
    except oss2.exceptions.NoSuchKey:
        print(f"✗ 远程文件 {REMOTE_JSON} 不存在")
    except Exception as e:
        print(f"✗ 下载 {REMOTE_JSON} 失败: {e}")
    
    # 2. 下载 images/ 目录下的所有图片
    # 确保本地目录存在
    if not os.path.exists(LOCAL_IMG_DIR):
        os.makedirs(LOCAL_IMG_DIR)
    
    try:
        # 列出远程images/目录下的所有文件
        for obj in oss2.ObjectIterator(bucket, prefix=REMOTE_IMG_PREFIX):
            if obj.key != REMOTE_IMG_PREFIX:  # 跳过目录本身
                filename = obj.key[len(REMOTE_IMG_PREFIX):]  # 去掉前缀
                local_path = os.path.join(LOCAL_IMG_DIR, filename)
                try:
                    bucket.get_object_to_file(obj.key, local_path)
                    print(f"✓ 下载 {obj.key} -> {local_path}")
                except Exception as e:
                    print(f"✗ 下载 {obj.key} 失败: {e}")
    except Exception as e:
        print(f"✗ 列出远程图片失败: {e}")
    
    # 3. 下载收藏夹文件
    try:
        bucket.get_object_to_file(REMOTE_FAVORITES_FILE, FAVORITES_FILE)
        print(f"✓ 下载 {REMOTE_FAVORITES_FILE} -> {FAVORITES_FILE}")
    except oss2.exceptions.NoSuchKey:
        print(f"✗ 远程文件 {REMOTE_FAVORITES_FILE} 不存在")
    except Exception as e:
        print(f"✗ 下载 {REMOTE_FAVORITES_FILE} 失败: {e}")
    
    # 4. 下载历史记录文件
    try:
        bucket.get_object_to_file(REMOTE_HISTORY_FILE, HISTORY_FILE)
        print(f"✓ 下载 {REMOTE_HISTORY_FILE} -> {HISTORY_FILE}")
    except oss2.exceptions.NoSuchKey:
        print(f"✗ 远程文件 {REMOTE_HISTORY_FILE} 不存在")
    except Exception as e:
        print(f"✗ 下载 {REMOTE_HISTORY_FILE} 失败: {e}")
    
    print("下载完成！")
    return True

def download_all(status_var=None, root=None):
    # 获取OSS bucket
    bucket = get_oss_bucket()
    if bucket is None:
        print("错误：无法获取OSS凭据，请先配置阿里云OSS凭据")
        prompt_for_oss_credentials()
        if status_var: status_var.set("OSS凭据未配置")
        return {"head": {}, "tail": {}}
    
    files_to_download = [
        (REMOTE_JSON, LOCAL_JSON, "tags.json"),
        (REMOTE_FAVORITES_FILE, FAVORITES_FILE, "收藏夹"),
        (REMOTE_HISTORY_FILE, HISTORY_FILE, "历史记录")
    ]
    
    data = {"head": {}, "tail": {}}
    
    # 下载开始提示
    if status_var:
        status_var.set("下载中...")
    if root:
        root.update_idletasks()

    # 下载各个文件
    for remote_file, local_file, display_name in files_to_download:
        try:
            print(f"📥 下载{display_name}")
            result = bucket.get_object(remote_file)
            raw = result.read()
            
            # 创建备份
            backup_file = local_file + ".backup"
            if os.path.exists(local_file):
                import shutil
                shutil.copy2(local_file, backup_file)
            
            with open(local_file, 'wb') as f:
                f.write(raw)
                
            # JSON文件格式校验
            if local_file.endswith('.json'):
                try:
                    loaded_data = json.loads(raw.decode("utf-8"))
                    if display_name == "tags.json":
                        data = loaded_data
                    print(f"✅ {display_name}健康")
                except Exception as e:
                    print(f"❌ {display_name}格式错误", e)
                    # 恢复备份
                    if os.path.exists(backup_file):
                        shutil.copy2(backup_file, local_file)
                    print(f"⚠️ 已恢复{display_name}备份文件")
            else:
                print(f"✅ {display_name}下载完成")
                
        except oss2.exceptions.NoSuchKey:
            print(f"⚠️ 云端{display_name}不存在，跳过")
        except Exception as e:
            print(f"❌ 下载{display_name}失败", e)
            if status_var:
                status_var.set(f"{display_name}下载失败")

    # 下载图片（原有逻辑）
    os.makedirs(LOCAL_IMG_DIR, exist_ok=True)
    total = 0
    bad_img = 0
    for obj in oss2.ObjectIterator(bucket, prefix=REMOTE_IMG_PREFIX):
        fname = obj.key[len(REMOTE_IMG_PREFIX):]
        if not fname:
            continue
        local_path = os.path.join(LOCAL_IMG_DIR, fname)
        try:
            result = bucket.get_object(obj.key)
            img_data = result.read()
            with open(local_path, "wb") as f:
                f.write(img_data)
            try:
                Image.open(io.BytesIO(img_data)).verify()
                print(f"✅ 下载图片：{fname}")
            except Exception as e:
                print(f"⚠️ 图片损坏或无法打开：{fname}")
                bad_img += 1
        except Exception as e:
            print(f"❌ 下载图片失败：{fname}", e)
        total += 1

    # 下载完成提示
    if status_var:
        status_var.set("下载完成")
    print(f"🎉 下载完毕，共{total}张图片")
    return data

# ========== 封装同步调用 ==========
def save_tags_with_sync(tags_data):
    with open(LOCAL_JSON, 'w', encoding='utf-8') as f:
        json.dump(tags_data, f, ensure_ascii=False, indent=2)
    upload_all()

def save_favorites_with_sync(favorites_data):
    with open(FAVORITES_FILE, 'w', encoding='utf-8') as f:
        json.dump(favorites_data, f, ensure_ascii=False, indent=2)
    upload_all()

def save_history_with_sync(history_data):
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history_data, f, ensure_ascii=False, indent=2)
    upload_all()

def load_tags_with_sync():
    return download_all()

# ========== 新增：单独同步函数 ==========
def sync_favorites_only(status_var=None, root=None):
    """仅同步收藏夹"""
    # 获取OSS bucket
    bucket = get_oss_bucket()
    if bucket is None:
        print("错误：无法获取OSS凭据，请先配置阿里云OSS凭据")
        prompt_for_oss_credentials()
        if status_var: status_var.set("OSS凭据未配置")
        return False
    
    try:
        if status_var:
            status_var.set("同步收藏夹中...")
        if root:
            root.update_idletasks()
            
        # 下载收藏夹
        try:
            result = bucket.get_object(REMOTE_FAVORITES_FILE)
            raw = result.read()
            with open(FAVORITES_FILE, 'wb') as f:
                f.write(raw)
            print("✅ 收藏夹同步完成")
            if status_var:
                status_var.set("收藏夹同步完成")
            return True
        except oss2.exceptions.NoSuchKey:
            print("⚠️ 云端收藏夹不存在")
            if status_var:
                status_var.set("云端收藏夹不存在")
            return False
    except Exception as e:
        print("❌ 收藏夹同步失败", e)
        if status_var:
            status_var.set("收藏夹同步失败")
        return False

def sync_history_only(status_var=None, root=None):
    """仅同步历史记录"""
    # 获取OSS bucket
    bucket = get_oss_bucket()
    if bucket is None:
        print("错误：无法获取OSS凭据，请先配置阿里云OSS凭据")
        prompt_for_oss_credentials()
        if status_var: status_var.set("OSS凭据未配置")
        return False
    
    try:
        if status_var:
            status_var.set("同步历史记录中...")
        if root:
            root.update_idletasks()
            
        # 下载历史记录
        try:
            result = bucket.get_object(REMOTE_HISTORY_FILE)
            raw = result.read()
            with open(HISTORY_FILE, 'wb') as f:
                f.write(raw)
            print("✅ 历史记录同步完成")
            if status_var:
                status_var.set("历史记录同步完成")
            return True
        except oss2.exceptions.NoSuchKey:
            print("⚠️ 云端历史记录不存在")
            if status_var:
                status_var.set("云端历史记录不存在")
            return False
    except Exception as e:
        print("❌ 历史记录同步失败", e)
        if status_var:
            status_var.set("历史记录同步失败")
        return False

def smart_sync():
    """智能同步：比较本地和远程的 tags.json，合并差异"""
    print("开始智能同步...")
    
    # 获取OSS bucket
    bucket = get_oss_bucket()
    if bucket is None:
        print("错误：无法获取OSS凭据，请先配置阿里云OSS凭据")
        prompt_for_oss_credentials()
        return False
    
    # 1. 先尝试下载远程的 tags.json
    remote_data = {}
    try:
        # 下载到临时文件
        temp_file = "temp_remote_tags.json"
        bucket.get_object_to_file(REMOTE_JSON, temp_file)
        
        with open(temp_file, 'r', encoding='utf-8') as f:
            remote_data = json.load(f)
        
        os.remove(temp_file)  # 删除临时文件
        print(f"✓ 成功获取远程 {REMOTE_JSON}")
    except oss2.exceptions.NoSuchKey:
        print(f"⚠️ 远程文件 {REMOTE_JSON} 不存在，将使用本地数据")
        remote_data = {}
    except Exception as e:
        print(f"✗ 获取远程 {REMOTE_JSON} 失败: {e}")
        return False
    
    # 2. 读取本地的 tags.json
    local_data = {}
    if os.path.exists(LOCAL_JSON):
        try:
            with open(LOCAL_JSON, 'r', encoding='utf-8') as f:
                local_data = json.load(f)
            print(f"✓ 成功读取本地 {LOCAL_JSON}")
        except Exception as e:
            print(f"✗ 读取本地 {LOCAL_JSON} 失败: {e}")
            return False
    else:
        print(f"⚠️ 本地文件 {LOCAL_JSON} 不存在，将使用远程数据")
    
    # 3. 合并数据
    merged_data = merge_tags_data(local_data, remote_data)
    
    # 4. 保存合并后的数据到本地
    try:
        with open(LOCAL_JSON, 'w', encoding='utf-8') as f:
            json.dump(merged_data, f, ensure_ascii=False, indent=2)
        print(f"✓ 保存合并数据到本地 {LOCAL_JSON}")
    except Exception as e:
        print(f"✗ 保存本地 {LOCAL_JSON} 失败: {e}")
        return False
    
    # 5. 上传合并后的数据到远程
    try:
        bucket.put_object_from_file(REMOTE_JSON, LOCAL_JSON)
        print(f"✓ 上传合并数据到远程 {REMOTE_JSON}")
    except Exception as e:
        print(f"✗ 上传到远程 {REMOTE_JSON} 失败: {e}")
        return False
    
    print("智能同步完成！")
    return True

def merge_tags_data(local_data, remote_data):
    """合并本地和远程的标签数据"""
    # 简单的合并策略：以本地数据为主，补充远程数据中本地没有的部分
    merged = local_data.copy()
    
    # 合并 head 部分
    if "head" in remote_data:
        if "head" not in merged:
            merged["head"] = {}
        for key, value in remote_data["head"].items():
            if key not in merged["head"]:
                merged["head"][key] = value
    
    # 合并 tail 部分
    if "tail" in remote_data:
        if "tail" not in merged:
            merged["tail"] = {}
        for key, value in remote_data["tail"].items():
            if key not in merged["tail"]:
                merged["tail"][key] = value
    
    return merged

# ========== 入口测试 ==========
if __name__ == "__main__":
    print("---- 下载云端所有内容 ----")
    download_all()
    # print("---- 上传所有内容到云端 ----")
    # upload_all()
# 在download_all函数中，确保有完整的状态反馈
# 函数已经支持status_var和root参数，无需修改
