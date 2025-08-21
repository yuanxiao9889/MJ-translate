#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
改进的更新管理器 - 增强网络健壮性
修复DNS解析失败和网络连接问题
"""

import os
import json
import requests
import zipfile
import shutil
import tempfile
import time
from pathlib import Path
from packaging import version

class UpdateManager:
    def __init__(self):
        """Initialize the UpdateManager with configuration."""
        self.config_path = Path(__file__).parent.parent / "config.json"
        self.config = self._load_config()
        self.current_version = self.config.get('version', '1.0.0')
    
    def _load_config(self):
        """Load configuration from config.json."""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error loading config: {e}")
        
        # Default configuration
        return {
            "version": "1.0.0",
            "github_owner": "yuanxiao9889",
            "github_repo": "MJ-translate"
        }
    
    def check_for_updates(self, max_retries=3):
        """Check for updates with enhanced network robustness."""
        repo_owner = self.config.get('github_owner')
        repo_name = self.config.get('github_repo')
        
        if not repo_owner or not repo_name:
            print("GitHub repository owner or name not configured.")
            return None, None
        
        # 多个API端点
        api_urls = [
            f"https://api.github.com/repos/{repo_owner}/{repo_name}/releases/latest",
            f"https://github.com/{repo_owner}/{repo_name}/releases/latest"
        ]
        
        session = requests.Session()
        session.trust_env = False
        session.proxies = {}
        headers = {
            'User-Agent': 'MJ-Translator-Update-Checker/1.0',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        for attempt in range(max_retries):
            print(f"正在检查更新... (尝试 {attempt + 1}/{max_retries})")
            
            for api_url in api_urls:
                try:
                    response = session.get(api_url, headers=headers, timeout=30)
                    
                    if response.status_code == 200:
                        latest_release = response.json()
                        latest_version = latest_release.get('tag_name', '').lstrip('v')
                        release_notes = latest_release.get('body', '')
                        
                        print(f"成功获取最新版本信息: {latest_version}")
                        
                        # 版本比较
                        try:
                            if version.parse(latest_version) > version.parse(self.current_version):
                                return latest_version, release_notes
                            else:
                                return None, None  # 已是最新版本
                        except Exception as ve:
                            print(f"版本比较失败: {ve}")
                            # 如果版本解析失败，仍然返回信息让用户决定
                            return latest_version, release_notes
                    
                except requests.exceptions.RequestException as e:
                    print(f"API请求失败 ({api_url}): {e}")
                    continue
                except Exception as e:
                    print(f"检查更新时发生错误: {e}")
                    continue
            
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 2
                print(f"等待 {wait_time} 秒后重试...")
                time.sleep(wait_time)
        
        print("检查更新失败，请检查网络连接")
        return None, None
    
    def _get_download_url_with_fallback(self, latest_release):
        """获取下载URL，使用多个备用方案"""
        repo_owner = self.config.get('github_owner')
        repo_name = self.config.get('github_repo')
        tag_name = latest_release.get('tag_name', 'latest')
        
        # 方案1: 用户上传的assets
        assets = latest_release.get('assets', [])
        for asset in assets:
            if asset['name'].endswith('.zip'):
                return asset['browser_download_url'], asset['name'], asset.get('size', 0)
        
        # 方案2: 使用GitHub的多个下载域名
        download_urls = [
            f"https://github.com/{repo_owner}/{repo_name}/archive/refs/tags/{tag_name}.zip",
            f"https://codeload.github.com/{repo_owner}/{repo_name}/zip/refs/tags/{tag_name}"
        ]
        
        file_name = f"{repo_name}-{tag_name}.zip"
        
        # 测试每个URL的可达性
        session = requests.Session()
        session.trust_env = False
        session.proxies = {}
        headers = {
            'User-Agent': 'MJ-Translator-Update-Checker/1.0'
        }
        
        for url in download_urls:
            try:
                print(f"测试下载URL: {url}")
                # 只发送HEAD请求测试连接
                response = session.head(url, headers=headers, timeout=10)
                if response.status_code in [200, 302]:
                    print(f"✓ URL可用: {url}")
                    return url, file_name, 0
            except Exception as e:
                print(f"✗ URL不可用: {url} - {e}")
                continue
        
        raise Exception("所有下载URL都不可用，请检查网络连接")
    
    def _download_with_retry(self, url, file_path, headers=None, max_retries=3):
        """带重试机制的下载"""
        session = requests.Session()
        session.trust_env = False
        session.proxies = {}
        
        if not headers:
            headers = {
                'User-Agent': 'MJ-Translator-Update-Checker/1.0',
                'Accept': 'application/octet-stream'
            }
        
        for attempt in range(max_retries):
            try:
                print(f"下载尝试 {attempt + 1}/{max_retries}: {url}")
                
                response = session.get(url, stream=True, headers=headers, timeout=60)
                response.raise_for_status()
                
                with open(file_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                
                print(f"✓ 下载成功: {file_path}")
                return True
                
            except Exception as e:
                print(f"✗ 下载失败 (尝试 {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2  # 递增等待时间
                    print(f"等待 {wait_time} 秒后重试...")
                    time.sleep(wait_time)
                else:
                    raise Exception(f"下载失败，已重试 {max_retries} 次: {e}")
        
        return False
    
    def download_and_apply_update(self, progress_callback=None):
        """Downloads and applies the latest update with enhanced network robustness."""
        repo_owner = self.config.get('github_owner')
        repo_name = self.config.get('github_repo')
        if not repo_owner or not repo_name:
            print("GitHub repository owner or name not configured.")
            return False

        api_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/releases/latest"
        backup_dir = None
        temp_dir = None
        download_path = None
        
        try:
            # Get latest release info
            if progress_callback:
                progress_callback(5, "获取更新信息", "正在连接GitHub API...")
            
            session = requests.Session()
            session.trust_env = False
            session.proxies = {}
            headers = {
                'User-Agent': 'MJ-Translator-Update-Checker/1.0',
                'Accept': 'application/vnd.github.v3+json'
            }
            
            response = session.get(api_url, headers=headers, timeout=30)
            response.raise_for_status()
            latest_release = response.json()
            
            # 使用改进的下载URL获取方法
            if progress_callback:
                progress_callback(10, "准备更新", "正在获取下载链接...")
            
            try:
                download_url, file_name, file_size = self._get_download_url_with_fallback(latest_release)
            except Exception as e:
                if progress_callback:
                    progress_callback(100, "更新失败", f"无法获取下载链接: {e}")
                else:
                    print(f"无法获取下载链接: {e}")
                return False
            
            # Create backup directory
            project_root = Path(__file__).parent.parent
            backup_dir = project_root / "backup_before_update"
            backup_dir.mkdir(exist_ok=True)
            
            if progress_callback:
                progress_callback(20, "创建备份", "正在备份当前版本...")
            else:
                print("Creating backup of current version...")
            self._backup_current_version(backup_dir)
            
            # Download the update with retry
            if progress_callback:
                progress_callback(30, "下载更新", f"正在下载 {file_name}...")
            else:
                print(f"Downloading {file_name} from {download_url}...")
            
            temp_dir = tempfile.mkdtemp()
            download_path = os.path.join(temp_dir, file_name)
            
            # 使用改进的下载方法
            self._download_with_retry(download_url, download_path, headers)
            
            if progress_callback:
                progress_callback(70, "下载完成", f"文件已下载到 {download_path}")
            else:
                print(f"Downloaded update to {download_path}")
            
            # Extract and apply update
            if progress_callback:
                progress_callback(80, "应用更新", "正在解压和应用更新...")
            else:
                print("Extracting and applying update...")
            self._extract_and_apply_update(download_path, project_root)
            
            if progress_callback:
                progress_callback(95, "清理文件", "正在清理临时文件...")
            else:
                print("Update applied successfully!")
            
            # Clean up
            self._cleanup_after_update(backup_dir, temp_dir)
            
            if progress_callback:
                progress_callback(100, "更新完成", "更新已成功应用！")
            else:
                print("Update completed successfully!")
            
            return True
            
        except Exception as e:
            if progress_callback:
                progress_callback(100, "更新失败", f"更新过程中发生错误: {str(e)}")
            else:
                print(f"Error during update: {e}")
                print("Rolling back to previous version...")
            
            if backup_dir and backup_dir.exists():
                self._rollback_update(backup_dir)
                print("Rollback completed.")
            
            # Clean up temp files
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
                
            return False
    
    def _backup_current_version(self, backup_dir):
        """Creates a backup of critical files before update."""
        project_root = Path(__file__).parent.parent
        
        # Files and directories to backup
        backup_items = [
            'main.py',
            'services/',
            'views/',
            'config.json',
            'requirements.txt'
        ]
        
        for item in backup_items:
            source_path = project_root / item
            if source_path.exists():
                dest_path = backup_dir / item
                if source_path.is_file():
                    dest_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source_path, dest_path)
                elif source_path.is_dir():
                    if dest_path.exists():
                        shutil.rmtree(dest_path)
                    shutil.copytree(source_path, dest_path)
    
    def _extract_and_apply_update(self, zip_path, project_root):
        """Extracts the update zip and applies it to the project."""
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            # Extract to temporary directory first
            temp_extract_dir = tempfile.mkdtemp()
            zip_ref.extractall(temp_extract_dir)
            
            # Find the actual project directory in the extracted files
            extracted_items = os.listdir(temp_extract_dir)
            if len(extracted_items) == 1 and os.path.isdir(os.path.join(temp_extract_dir, extracted_items[0])):
                # If there's a single directory, use that as the source
                source_dir = os.path.join(temp_extract_dir, extracted_items[0])
            else:
                # Otherwise, use the temp directory directly
                source_dir = temp_extract_dir
            
            # Copy files from extracted directory to project root
            for item in os.listdir(source_dir):
                source_item = os.path.join(source_dir, item)
                dest_item = project_root / item
                
                if os.path.isfile(source_item):
                    shutil.copy2(source_item, dest_item)
                elif os.path.isdir(source_item):
                    if dest_item.exists():
                        shutil.rmtree(dest_item)
                    shutil.copytree(source_item, dest_item)
            
            # Clean up temp extraction directory
            shutil.rmtree(temp_extract_dir, ignore_errors=True)
    
    def _rollback_update(self, backup_dir):
        """Rolls back to the backed up version."""
        project_root = Path(__file__).parent.parent
        
        for item in backup_dir.iterdir():
            dest_path = project_root / item.name
            
            if item.is_file():
                shutil.copy2(item, dest_path)
            elif item.is_dir():
                if dest_path.exists():
                    shutil.rmtree(dest_path)
                shutil.copytree(item, dest_path)
    
    def _cleanup_after_update(self, backup_dir, temp_dir):
        """Cleans up temporary files after successful update."""
        # Remove backup directory
        if backup_dir and backup_dir.exists():
            shutil.rmtree(backup_dir, ignore_errors=True)
        
        # Remove temp directory
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
