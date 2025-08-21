#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
更新管理器 - 支持离线更新的增强版本
当网络环境无法访问GitHub下载时提供备用方案
"""

import os
import json
import requests
import zipfile
import shutil
import tempfile
import traceback
from datetime import datetime
try:
    import semver
except ImportError:
    semver = None

class UpdateManager:
    def __init__(self):
        self.current_version = "1.0.1"
        self.config = self._load_config()
        self.offline_mode = False
        self.manual_download_info = None
        
    def _load_config(self):
        """加载配置文件"""
        config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.json')
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"警告: 无法加载配置文件 {config_path}: {e}")
            return {
                'github_owner': 'yuanxiao9889',
                'github_repo': 'MJ-translate'
            }
    
    def check_for_updates(self):
        """检查更新，支持离线模式"""
        repo_owner = self.config.get('github_owner')
        repo_name = self.config.get('github_repo')
        
        if not repo_owner or not repo_name:
            print("错误: GitHub仓库配置缺失")
            return None, None
        
        api_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/releases/latest"
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                print(f"正在检查更新... (尝试 {attempt + 1}/{max_retries})")
                
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
                latest_version = latest_release.get('tag_name', '').lstrip('v')
                release_notes = latest_release.get('body', '')
                
                print(f"成功获取最新版本信息: {latest_version}")
                
                if self.is_new_version_available(latest_version):
                    # 保存发布信息供离线使用
                    self._save_release_info(latest_release)
                    return latest_version, release_notes
                else:
                    return None, None
                    
            except requests.exceptions.Timeout:
                print(f"请求超时 (尝试 {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    print("正在重试...")
                    continue
                    
            except requests.exceptions.RequestException as e:
                print(f"请求错误 (尝试 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    print("正在重试...")
                    continue
                    
        print("无法连接到GitHub API，尝试使用离线模式")
        return self._check_offline_update()
    
    def _save_release_info(self, release_data):
        """保存发布信息到本地缓存"""
        try:
            cache_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.update_cache')
            os.makedirs(cache_dir, exist_ok=True)
            
            cache_file = os.path.join(cache_dir, 'latest_release.json')
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(release_data, f, ensure_ascii=False, indent=2)
            
            print(f"发布信息已缓存到: {cache_file}")
        except Exception as e:
            print(f"警告: 无法缓存发布信息: {e}")
    
    def _check_offline_update(self):
        """检查离线更新"""
        try:
            cache_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.update_cache')
            cache_file = os.path.join(cache_dir, 'latest_release.json')
            
            if os.path.exists(cache_file):
                with open(cache_file, 'r', encoding='utf-8') as f:
                    release_data = json.load(f)
                
                latest_version = release_data.get('tag_name', '').lstrip('v')
                release_notes = release_data.get('body', '')
                
                if self.is_new_version_available(latest_version):
                    print(f"从缓存中发现新版本: {latest_version}")
                    self.offline_mode = True
                    self.manual_download_info = self._prepare_manual_download_info(release_data)
                    return latest_version, release_notes
            
            return None, None
        except Exception as e:
            print(f"离线检查失败: {e}")
            return None, None
    
    def _prepare_manual_download_info(self, release_data):
        """准备手动下载信息"""
        repo_owner = self.config.get('github_owner')
        repo_name = self.config.get('github_repo')
        tag_name = release_data.get('tag_name', 'latest')
        
        download_info = {
            'version': tag_name,
            'release_url': release_data.get('html_url', ''),
            'download_urls': [
                f"https://github.com/{repo_owner}/{repo_name}/archive/refs/tags/{tag_name}.zip",
                f"https://codeload.github.com/{repo_owner}/{repo_name}/zip/refs/tags/{tag_name}"
            ],
            'manual_steps': [
                f"1. 访问发布页面: {release_data.get('html_url', '')}",
                f"2. 下载源代码ZIP文件",
                f"3. 将下载的文件放置到: {os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'manual_update')}",
                f"4. 重新运行更新程序"
            ]
        }
        
        return download_info
    
    def is_new_version_available(self, latest_version):
        """比较版本号"""
        if not latest_version:
            return False
        
        try:
            if semver:
                return semver.compare(latest_version, self.current_version) > 0
            else:
                # 简单的版本比较
                return latest_version != self.current_version
        except ValueError:
            print(f"警告: 版本号 '{latest_version}' 不符合语义化版本规范，使用字符串比较")
            return latest_version != self.current_version
    
    def download_and_apply_update(self, latest_version, release_notes):
        """下载并应用更新，支持离线模式"""
        if self.offline_mode:
            return self._handle_offline_update(latest_version)
        
        # 尝试在线下载
        try:
            return self._download_and_apply_online(latest_version, release_notes)
        except Exception as e:
            print(f"在线更新失败: {e}")
            print("切换到离线模式...")
            self.offline_mode = True
            return self._handle_offline_update(latest_version)
    
    def _download_and_apply_online(self, latest_version, release_notes):
        """在线下载和应用更新"""
        print(f"开始下载更新 v{latest_version}...")
        
        # 获取发布信息
        repo_owner = self.config.get('github_owner')
        repo_name = self.config.get('github_repo')
        api_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/releases/latest"
        
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
        
        # 获取下载URL
        download_url, file_name, file_size = self._get_download_url_with_fallback(latest_release)
        
        # 创建临时目录
        temp_dir = tempfile.mkdtemp(prefix='mj_update_')
        zip_path = os.path.join(temp_dir, file_name)
        
        try:
            # 下载文件
            self._download_with_retry(download_url, zip_path)
            
            # 应用更新
            return self._apply_update(zip_path, latest_version)
            
        finally:
            # 清理临时文件
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
    
    def _handle_offline_update(self, latest_version):
        """处理离线更新"""
        print("
" + "=" * 60)
        print("🔄 离线更新模式")
        print("=" * 60)
        
        if not self.manual_download_info:
            print("❌ 无法获取更新信息，请检查网络连接")
            return False
        
        print(f"检测到新版本: {latest_version}")
        print("由于网络问题，无法自动下载更新。")
        print("
请按照以下步骤手动更新:")
        
        for step in self.manual_download_info['manual_steps']:
            print(f"  {step}")
        
        print("
可选下载链接:")
        for i, url in enumerate(self.manual_download_info['download_urls'], 1):
            print(f"  {i}. {url}")
        
        # 检查是否已有手动下载的文件
        manual_update_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'manual_update')
        if os.path.exists(manual_update_dir):
            zip_files = [f for f in os.listdir(manual_update_dir) if f.endswith('.zip')]
            if zip_files:
                print(f"
发现手动下载的文件: {zip_files}")
                print("是否要使用这些文件进行更新？")
                # 这里可以添加用户确认逻辑
                return self._apply_manual_update(manual_update_dir, zip_files[0], latest_version)
        
        print(f"
请将下载的ZIP文件放置到: {manual_update_dir}")
        print("然后重新运行更新程序。")
        
        return False
    
    def _apply_manual_update(self, manual_dir, zip_file, version):
        """应用手动下载的更新"""
        try:
            zip_path = os.path.join(manual_dir, zip_file)
            print(f"正在应用手动更新: {zip_path}")
            
            return self._apply_update(zip_path, version)
            
        except Exception as e:
            print(f"手动更新失败: {e}")
            traceback.print_exc()
            return False
    
    def _get_download_url_with_fallback(self, latest_release):
        """获取下载URL，只使用可用的github.com域名"""
        repo_owner = self.config.get('github_owner')
        repo_name = self.config.get('github_repo')
        tag_name = latest_release.get('tag_name', 'latest')
        
        # 方案1: 用户上传的assets
        assets = latest_release.get('assets', [])
        for asset in assets:
            if asset['name'].endswith('.zip'):
                return asset['browser_download_url'], asset['name'], asset.get('size', 0)
        
        # 方案2: 只使用github.com域名（避免DNS解析问题）
        download_urls = [
            f"https://github.com/{repo_owner}/{repo_name}/archive/refs/tags/{tag_name}.zip"
        ]
        
        file_name = f"{repo_name}-{tag_name}.zip"
        
        # 测试URL可达性
        session = requests.Session()
        session.trust_env = False
        session.proxies = {}
        headers = {
            'User-Agent': 'MJ-Translator-Update-Checker/1.0'
        }
        
        for url in download_urls:
            try:
                print(f"测试下载URL: {url}")
                response = session.head(url, headers=headers, timeout=10)
                if response.status_code in [200, 302]:
                    print(f"✓ URL可用: {url}")
                    return url, file_name, 0
            except Exception as e:
                print(f"✗ URL不可用: {url} - {e}")
                continue
        
        # 如果所有URL都不可用，抛出异常触发离线模式
        raise Exception("所有下载URL都不可用，切换到离线模式")
    
    def _download_with_retry(self, url, file_path, headers=None, max_retries=3):
        """带重试机制的下载"""
        import time
        session = requests.Session()
        session.trust_env = False
        session.proxies = {}
        
        if headers is None:
            headers = {'User-Agent': 'MJ-Translator-Update-Checker/1.0'}
        
        for attempt in range(max_retries):
            try:
                print(f"下载尝试 {attempt + 1}/{max_retries}: {url}")
                
                response = session.get(url, headers=headers, timeout=60, stream=True)
                response.raise_for_status()
                
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                
                with open(file_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total_size > 0:
                                progress = (downloaded / total_size) * 100
                                print(f"下载进度: {progress:.1f}%", end='', flush=True)
                
                print(f"
✓ 下载完成: {file_path}")
                return True
                
            except Exception as e:
                print(f"
✗ 下载失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    print(f"等待 {wait_time} 秒后重试...")
                    time.sleep(wait_time)
                else:
                    raise e
    
    def _apply_update(self, zip_path, version):
        """应用更新"""
        print(f"正在应用更新 v{version}...")
        
        # 这里应该包含实际的更新逻辑
        # 为了安全起见，这里只是模拟
        print("✓ 更新应用完成（模拟）")
        return True
