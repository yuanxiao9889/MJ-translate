"""安全凭据管理服务

此模块提供安全的凭据存储和管理功能，支持：
- 翻译API密钥管理（百度、智谱AI等）
- 阿里云存储密钥管理
- 密钥加密存储
- 凭据的增删改查操作
"""

from __future__ import annotations

import os
import json
import base64
import hashlib
from typing import Dict, List, Any, Optional, Tuple
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from .file_utils import safe_json_load, safe_json_save
from .logger import logger

class CredentialsManager:
    """安全凭据管理器"""
    
    def __init__(self, config_dir: str = None):
        """初始化凭据管理器
        
        Args:
            config_dir: 配置文件目录，默认为项目根目录
        """
        if config_dir is None:
            config_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        self.config_dir = config_dir
        self.credentials_file = os.path.join(config_dir, "credentials.json")
        self.key_file = os.path.join(config_dir, ".key")
        
        # 支持的凭据类型及其字段定义
        self.credential_types = {
            "baidu_translate": {
                "name": "百度翻译",
                "fields": [
                    {"key": "app_id", "label": "App ID", "type": "text", "required": True},
                    {"key": "app_key", "label": "App Key", "type": "password", "required": True}
                ]
            },
            "zhipu_ai": {
                "name": "智谱AI",
                "fields": [
                    {"key": "api_key", "label": "API Key", "type": "password", "required": True}
                ]
            },
            "zhipu_glm45": {
                "name": "智谱GLM-4.5",
                "fields": [
                    {"key": "api_key", "label": "API Key", "type": "password", "required": True}
                ]
            },
            "aliyun_oss": {
                "name": "阿里云OSS",
                "fields": [
                    {"key": "access_key_id", "label": "Access Key ID", "type": "text", "required": True},
                    {"key": "access_key_secret", "label": "Access Key Secret", "type": "password", "required": True},
                    {"key": "region", "label": "地域", "type": "select", "required": True, "options": [
                        {"value": "oss-cn-hangzhou.aliyuncs.com", "label": "华东1（杭州）"},
                        {"value": "oss-cn-shanghai.aliyuncs.com", "label": "华东2（上海）"},
                        {"value": "oss-cn-qingdao.aliyuncs.com", "label": "华北1（青岛）"},
                        {"value": "oss-cn-beijing.aliyuncs.com", "label": "华北2（北京）"},
                        {"value": "oss-cn-zhangjiakou.aliyuncs.com", "label": "华北3（张家口）"},
                        {"value": "oss-cn-huhehaote.aliyuncs.com", "label": "华北5（呼和浩特）"},
                        {"value": "oss-cn-wulanchabu.aliyuncs.com", "label": "华北6（乌兰察布）"},
                        {"value": "oss-cn-shenzhen.aliyuncs.com", "label": "华南1（深圳）"},
                        {"value": "oss-cn-heyuan.aliyuncs.com", "label": "华南2（河源）"},
                        {"value": "oss-cn-guangzhou.aliyuncs.com", "label": "华南3（广州）"},
                        {"value": "oss-cn-chengdu.aliyuncs.com", "label": "西南1（成都）"},
                        {"value": "oss-cn-hongkong.aliyuncs.com", "label": "中国香港"},
                        {"value": "oss-us-west-1.aliyuncs.com", "label": "美国西部1（硅谷）"},
                        {"value": "oss-us-east-1.aliyuncs.com", "label": "美国东部1（弗吉尼亚）"},
                        {"value": "oss-ap-southeast-1.aliyuncs.com", "label": "亚太东南1（新加坡）"},
                        {"value": "oss-ap-southeast-2.aliyuncs.com", "label": "亚太东南2（悉尼）"},
                        {"value": "oss-ap-southeast-3.aliyuncs.com", "label": "亚太东南3（吉隆坡）"},
                        {"value": "oss-ap-southeast-5.aliyuncs.com", "label": "亚太东南5（雅加达）"},
                        {"value": "oss-ap-northeast-1.aliyuncs.com", "label": "亚太东北1（日本）"},
                        {"value": "oss-ap-south-1.aliyuncs.com", "label": "亚太南部1（孟买）"},
                        {"value": "oss-eu-central-1.aliyuncs.com", "label": "欧洲中部1（法兰克福）"},
                        {"value": "oss-eu-west-1.aliyuncs.com", "label": "英国（伦敦）"},
                        {"value": "oss-me-east-1.aliyuncs.com", "label": "中东东部1（迪拜）"}
                    ]},
                    {"key": "bucket_name", "label": "Bucket Name", "type": "text", "required": True}
                ]
            }
        }
        
        self._cipher_suite = None
        self._credentials_cache = None
        
    def _get_or_create_key(self) -> bytes:
        """获取或创建加密密钥"""
        if os.path.exists(self.key_file):
            try:
                with open(self.key_file, 'rb') as f:
                    return f.read()
            except Exception as e:
                logger.error(f"读取密钥文件失败: {e}")
        
        # 创建新密钥
        password = b"mj_translator_default_key"  # 可以后续改为用户设置的密码
        salt = os.urandom(16)
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password))
        
        try:
            with open(self.key_file, 'wb') as f:
                f.write(salt + key)
            return salt + key
        except Exception as e:
            logger.error(f"创建密钥文件失败: {e}")
            return key
    
    def _get_cipher_suite(self) -> Fernet:
        """获取加密套件"""
        if self._cipher_suite is None:
            key_data = self._get_or_create_key()
            if len(key_data) > 32:
                # 包含salt的情况
                key = key_data[16:]
            else:
                key = key_data
            self._cipher_suite = Fernet(key)
        return self._cipher_suite
    
    def _encrypt_data(self, data: str) -> str:
        """加密数据"""
        try:
            cipher_suite = self._get_cipher_suite()
            encrypted_data = cipher_suite.encrypt(data.encode('utf-8'))
            return base64.urlsafe_b64encode(encrypted_data).decode('utf-8')
        except Exception as e:
            logger.error(f"数据加密失败: {e}")
            return data  # 加密失败时返回原数据
    
    def _decrypt_data(self, encrypted_data: str) -> str:
        """解密数据"""
        try:
            cipher_suite = self._get_cipher_suite()
            decoded_data = base64.urlsafe_b64decode(encrypted_data.encode('utf-8'))
            decrypted_data = cipher_suite.decrypt(decoded_data)
            return decrypted_data.decode('utf-8')
        except Exception as e:
            logger.error(f"数据解密失败: {e}")
            return encrypted_data  # 解密失败时返回原数据
    
    def _load_credentials(self) -> Dict[str, List[Dict[str, Any]]]:
        """加载凭据数据"""
        if self._credentials_cache is not None:
            return self._credentials_cache
        
        default_data = {cred_type: [] for cred_type in self.credential_types.keys()}
        encrypted_data = safe_json_load(self.credentials_file, default_data)
        
        # 解密敏感字段
        decrypted_data = {}
        for cred_type, credentials in encrypted_data.items():
            decrypted_credentials = []
            for cred in credentials:
                decrypted_cred = cred.copy()
                # 解密密码类型字段
                if cred_type in self.credential_types:
                    for field in self.credential_types[cred_type]["fields"]:
                        if field["type"] == "password" and field["key"] in decrypted_cred:
                            if decrypted_cred[field["key"]].startswith("enc:"):
                                encrypted_value = decrypted_cred[field["key"]][4:]
                                decrypted_cred[field["key"]] = self._decrypt_data(encrypted_value)
                decrypted_credentials.append(decrypted_cred)
            decrypted_data[cred_type] = decrypted_credentials
        
        self._credentials_cache = decrypted_data
        return decrypted_data
    
    def _save_credentials(self, credentials: Dict[str, List[Dict[str, Any]]]) -> bool:
        """保存凭据数据"""
        try:
            # 加密敏感字段
            encrypted_data = {}
            for cred_type, cred_list in credentials.items():
                encrypted_credentials = []
                for cred in cred_list:
                    encrypted_cred = cred.copy()
                    # 加密密码类型字段
                    if cred_type in self.credential_types:
                        for field in self.credential_types[cred_type]["fields"]:
                            if field["type"] == "password" and field["key"] in encrypted_cred:
                                if not encrypted_cred[field["key"]].startswith("enc:"):
                                    encrypted_value = self._encrypt_data(encrypted_cred[field["key"]])
                                    encrypted_cred[field["key"]] = f"enc:{encrypted_value}"
                    encrypted_credentials.append(encrypted_cred)
                encrypted_data[cred_type] = encrypted_credentials
            
            success = safe_json_save(self.credentials_file, encrypted_data)
            if success:
                self._credentials_cache = credentials
            return success
        except Exception as e:
            logger.error(f"保存凭据失败: {e}")
            return False
    
    def get_credential_types(self) -> Dict[str, Dict[str, Any]]:
        """获取支持的凭据类型"""
        return self.credential_types.copy()
    
    def get_credentials(self, cred_type: str = None) -> Dict[str, List[Dict[str, Any]]]:
        """获取凭据列表
        
        Args:
            cred_type: 凭据类型，为None时返回所有类型
        
        Returns:
            凭据字典，key为凭据类型，value为凭据列表
        """
        credentials = self._load_credentials()
        if cred_type:
            return {cred_type: credentials.get(cred_type, [])}
        return credentials
    
    def add_credential(self, cred_type: str, credential_data: Dict[str, Any]) -> Tuple[bool, str]:
        """添加凭据
        
        Args:
            cred_type: 凭据类型
            credential_data: 凭据数据
        
        Returns:
            (成功标志, 错误信息)
        """
        if cred_type not in self.credential_types:
            return False, f"不支持的凭据类型: {cred_type}"
        
        # 验证必填字段
        type_config = self.credential_types[cred_type]
        for field in type_config["fields"]:
            if field["required"] and not credential_data.get(field["key"]):
                return False, f"缺少必填字段: {field['label']}"
        
        credentials = self._load_credentials()
        
        # 添加元数据
        new_credential = credential_data.copy()
        new_credential.update({
            "id": self._generate_credential_id(),
            "name": credential_data.get("name", f"{type_config['name']}_{len(credentials[cred_type]) + 1}"),
            "created_at": self._get_current_timestamp(),
            "disabled": False
        })
        
        credentials[cred_type].append(new_credential)
        
        if self._save_credentials(credentials):
            return True, "凭据添加成功"
        else:
            return False, "保存凭据失败"
    
    def update_credential(self, cred_type: str, credential_id: str, 
                         credential_data: Dict[str, Any]) -> Tuple[bool, str]:
        """更新凭据
        
        Args:
            cred_type: 凭据类型
            credential_id: 凭据ID
            credential_data: 新的凭据数据
        
        Returns:
            (成功标志, 错误信息)
        """
        if cred_type not in self.credential_types:
            return False, f"不支持的凭据类型: {cred_type}"
        
        credentials = self._load_credentials()
        cred_list = credentials.get(cred_type, [])
        
        # 查找要更新的凭据
        target_index = -1
        for i, cred in enumerate(cred_list):
            if cred.get("id") == credential_id:
                target_index = i
                break
        
        if target_index == -1:
            return False, "未找到指定的凭据"
        
        # 验证必填字段
        type_config = self.credential_types[cred_type]
        for field in type_config["fields"]:
            if field["required"] and not credential_data.get(field["key"]):
                return False, f"缺少必填字段: {field['label']}"
        
        # 更新凭据，保留元数据
        updated_credential = cred_list[target_index].copy()
        updated_credential.update(credential_data)
        updated_credential["updated_at"] = self._get_current_timestamp()
        
        credentials[cred_type][target_index] = updated_credential
        
        if self._save_credentials(credentials):
            return True, "凭据更新成功"
        else:
            return False, "保存凭据失败"
    
    def delete_credential(self, cred_type: str, credential_id: str) -> Tuple[bool, str]:
        """删除凭据
        
        Args:
            cred_type: 凭据类型
            credential_id: 凭据ID
        
        Returns:
            (成功标志, 错误信息)
        """
        credentials = self._load_credentials()
        cred_list = credentials.get(cred_type, [])
        
        # 查找要删除的凭据
        target_index = -1
        for i, cred in enumerate(cred_list):
            if cred.get("id") == credential_id:
                target_index = i
                break
        
        if target_index == -1:
            return False, "未找到指定的凭据"
        
        credentials[cred_type].pop(target_index)
        
        if self._save_credentials(credentials):
            return True, "凭据删除成功"
        else:
            return False, "保存凭据失败"
    
    def toggle_credential_status(self, cred_type: str, credential_id: str) -> Tuple[bool, str]:
        """切换凭据启用/禁用状态
        
        Args:
            cred_type: 凭据类型
            credential_id: 凭据ID
        
        Returns:
            (成功标志, 状态信息)
        """
        credentials = self._load_credentials()
        cred_list = credentials.get(cred_type, [])
        
        # 查找要切换的凭据
        target_index = -1
        for i, cred in enumerate(cred_list):
            if cred.get("id") == credential_id:
                target_index = i
                break
        
        if target_index == -1:
            return False, "未找到指定的凭据"
        
        current_status = credentials[cred_type][target_index].get("disabled", False)
        credentials[cred_type][target_index]["disabled"] = not current_status
        credentials[cred_type][target_index]["updated_at"] = self._get_current_timestamp()
        
        if self._save_credentials(credentials):
            new_status = "禁用" if not current_status else "启用"
            return True, f"凭据已{new_status}"
        else:
            return False, "保存凭据失败"
    
    def get_masked_credential(self, cred_type: str, credential_id: str) -> Optional[Dict[str, Any]]:
        """获取脱敏的凭据信息（用于显示）
        
        Args:
            cred_type: 凭据类型
            credential_id: 凭据ID
        
        Returns:
            脱敏的凭据信息
        """
        credentials = self._load_credentials()
        cred_list = credentials.get(cred_type, [])
        
        for cred in cred_list:
            if cred.get("id") == credential_id:
                masked_cred = cred.copy()
                
                # 脱敏敏感字段
                if cred_type in self.credential_types:
                    for field in self.credential_types[cred_type]["fields"]:
                        if field["type"] == "password" and field["key"] in masked_cred:
                            value = masked_cred[field["key"]]
                            if len(value) > 8:
                                masked_cred[field["key"]] = value[:4] + "*" * (len(value) - 8) + value[-4:]
                            else:
                                masked_cred[field["key"]] = "*" * len(value)
                
                return masked_cred
        
        return None
    
    def _generate_credential_id(self) -> str:
        """生成凭据ID"""
        import uuid
        return str(uuid.uuid4())[:8]
    
    def _get_current_timestamp(self) -> str:
        """获取当前时间戳"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def migrate_from_old_config(self, old_api_config: Dict[str, List[Dict[str, Any]]] = None, old_oss_config: Dict[str, Any] = None) -> bool:
        """从旧的API配置和OSS配置迁移数据
        
        Args:
            old_api_config: 旧的API配置数据
            old_oss_config: 旧的OSS配置数据
        
        Returns:
            迁移是否成功
        """
        try:
            credentials = self._load_credentials()
            migrated = False
            
            # 如果没有传入旧配置，尝试从文件加载
            if old_api_config is None:
                api_config_file = os.path.join(self.config_dir, "apis.json")
                if os.path.exists(api_config_file):
                    old_api_config = safe_json_load(api_config_file, {})
                    logger.info(f"从 {api_config_file} 加载旧API配置")
            
            if old_oss_config is None:
                oss_config_file = os.path.join(self.config_dir, "oss_config.json")
                if os.path.exists(oss_config_file):
                    old_oss_config = safe_json_load(oss_config_file, {})
                    logger.info(f"从 {oss_config_file} 加载旧OSS配置")
            
            # 迁移API配置
            if old_api_config:
                type_mapping = {
                    "baidu": "baidu_translate",
                    "zhipu": "zhipu_ai",
                    "zhipu-glm45": "zhipu_glm45"
                }
                
                for old_type, new_type in type_mapping.items():
                    if old_type in old_api_config:
                        for old_cred in old_api_config[old_type]:
                            # 检查是否已存在相同凭据
                            exists = False
                            for existing_cred in credentials[new_type]:
                                if old_type == "baidu":
                                    if (existing_cred.get("app_id") == old_cred.get("app_id") and
                                        existing_cred.get("app_key") == old_cred.get("app_key")):
                                        exists = True
                                        break
                                else:
                                    if existing_cred.get("api_key") == old_cred.get("api_key"):
                                        exists = True
                                        break
                            
                            if not exists:
                                new_cred = old_cred.copy()
                                new_cred.update({
                                    "id": self._generate_credential_id(),
                                    "name": f"{self.credential_types[new_type]['name']}_{len(credentials[new_type]) + 1}",
                                    "created_at": self._get_current_timestamp()
                                })
                                credentials[new_type].append(new_cred)
                                migrated = True
            
            # 迁移OSS配置
            if old_oss_config:
                # 检查是否已存在相同的OSS配置
                exists = False
                for existing_cred in credentials["aliyun_oss"]:
                    if (existing_cred.get("access_key_id") == old_oss_config.get("ACCESS_KEY_ID") and
                        existing_cred.get("bucket_name") == old_oss_config.get("BUCKET_NAME")):
                        exists = True
                        break
                
                if not exists:
                    # 添加OSS凭据
                    new_oss_cred = {
                        "id": self._generate_credential_id(),
                        "name": f"阿里云OSS_{len(credentials['aliyun_oss']) + 1}",
                        "disabled": False,
                        "created_at": self._get_current_timestamp(),
                        "access_key_id": old_oss_config.get("ACCESS_KEY_ID", ""),
                        "access_key_secret": old_oss_config.get("ACCESS_KEY_SECRET", ""),
                        "region": old_oss_config.get("ENDPOINT", "oss-cn-shenzhen.aliyuncs.com"),
                        "bucket_name": old_oss_config.get("BUCKET_NAME", "")
                    }
                    credentials["aliyun_oss"].append(new_oss_cred)
                    migrated = True
            
            if migrated:
                self._save_credentials(credentials)
                logger.info("成功从旧配置迁移凭据")
            
            return True
            
        except Exception as e:
            logger.error(f"迁移配置失败: {e}")
            return False
    
    def get_active_credential(self, cred_type: str) -> Optional[Dict[str, Any]]:
        """获取指定类型的第一个可用凭据
        
        Args:
            cred_type: 凭据类型
        
        Returns:
            可用的凭据信息，如果没有则返回None
        """
        credentials = self._load_credentials()
        cred_list = credentials.get(cred_type, [])
        
        for cred in cred_list:
            if not cred.get("disabled", False):
                return cred
        
        return None
    
    def get_credential_by_id(self, cred_type: str, credential_id: str) -> Optional[Dict[str, Any]]:
        """根据ID获取凭据
        
        Args:
            cred_type: 凭据类型
            credential_id: 凭据ID
        
        Returns:
            凭据信息，如果没有则返回None
        """
        credentials = self._load_credentials()
        cred_list = credentials.get(cred_type, [])
        
        for cred in cred_list:
            if cred.get("id") == credential_id:
                return cred
        
        return None

# 全局凭据管理器实例
_credentials_manager = None

def get_credentials_manager() -> CredentialsManager:
    """获取全局凭据管理器实例"""
    global _credentials_manager
    if _credentials_manager is None:
        _credentials_manager = CredentialsManager()
        # 自动迁移旧配置
        _credentials_manager.migrate_from_old_config()
    return _credentials_manager