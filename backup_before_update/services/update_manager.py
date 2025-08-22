import requests
import semver
import json
import os
import zipfile
import shutil
import tempfile
from pathlib import Path
from services import __version__ as current_version

class UpdateManager:
    def __init__(self):
        self.config = self._load_config()
        self.current_version = current_version
        self.offline_mode = False
        self.manual_download_info = None

    def _load_config(self):
        config_path = os.path.join(os.path.dirname(__file__), '..', 'config.json')
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def check_for_updates(self):
        """Checks for new releases on GitHub."""
        repo_owner = self.config.get('github_owner')
        repo_name = self.config.get('github_repo')
        if not repo_owner or not repo_name:
            print("GitHub repository owner or name not configured.")
            return None, None

        api_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/releases/latest"
        
        # 配置请求参数，禁用代理并设置超时
        session = requests.Session()
        session.trust_env = False  # 禁用环境变量中的代理设置
        session.proxies = {}  # 清空代理设置
        
        headers = {
            'User-Agent': 'MJ-Translator-Update-Checker/1.0',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        # 重试机制
        max_retries = 3
        for attempt in range(max_retries):
            try:
                print(f"正在检查更新... (尝试 {attempt + 1}/{max_retries})")
                response = session.get(
                    api_url, 
                    headers=headers,
                    timeout=30,  # 30秒超时
                    proxies={}  # 确保不使用代理
                )
                response.raise_for_status()
                latest_release = response.json()
                latest_version = latest_release['tag_name'].lstrip('v')
                release_notes = latest_release['body']
                print(f"成功获取最新版本信息: {latest_version}")
                
                # 保存发布信息供离线使用
                self._save_release_info(latest_release)
                
                return latest_version, release_notes
                
            except requests.exceptions.ProxyError as e:
                print(f"代理连接错误 (尝试 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    print("正在重试...")
                    continue
                else:
                    print("所有重试均失败，请检查网络连接或禁用代理")
                    
            except requests.exceptions.Timeout as e:
                print(f"请求超时 (尝试 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    print("正在重试...")
                    continue
                    
            except requests.exceptions.ConnectionError as e:
                print(f"连接错误 (尝试 {attempt + 1}/{max_retries}): {e}")
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

    def is_new_version_available(self, latest_version):
        """Compares the latest version with the current version."""
        if not latest_version:
            return False
        
        try:
            # 尝试使用语义化版本比较
            return semver.compare(latest_version, self.current_version) > 0
        except ValueError:
            # 如果版本号不符合语义化版本规范，使用字符串比较
            print(f"警告: 版本号 '{latest_version}' 不符合语义化版本规范，使用字符串比较")
            # 简单的字符串比较，如果不同就认为有新版本
            return latest_version != self.current_version

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
        
        # 方案2: 只使用可用的github.com域名（避免codeload.github.com DNS解析问题）
        download_urls = [
            f"https://github.com/{repo_owner}/{repo_name}/archive/refs/tags/{tag_name}.zip"
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
        import time
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
            # 配置网络请求参数
            session = requests.Session()
            session.trust_env = False
            session.proxies = {}
            headers = {
                'User-Agent': 'MJ-Translator-Update-Checker/1.0',
                'Accept': 'application/vnd.github.v3+json'
            }
            
            # Get latest release info
            if progress_callback:
                progress_callback(5, "获取更新信息", "正在连接GitHub API...")
            response = session.get(api_url, headers=headers, timeout=30, proxies={})
            response.raise_for_status()
            latest_release = response.json()
            
            # Get download URL with fallback
            if progress_callback:
                progress_callback(10, "获取下载链接", "正在解析下载地址...")
            
            download_url, file_name, file_size = self._get_download_url_with_fallback(latest_release)
            print(f"选择的下载URL: {download_url}")
            print(f"文件名: {file_name}")
            if file_size > 0:
                print(f"文件大小: {file_size / 1024 / 1024:.2f} MB")
            
            # Create backup directory
            project_root = Path(__file__).parent.parent
            backup_dir = project_root / "backup_before_update"
            backup_dir.mkdir(exist_ok=True)
            
            if progress_callback:
                progress_callback(20, "创建备份", "正在备份当前版本...")
            else:
                print("Creating backup of current version...")
            self._backup_current_version(backup_dir)
            
            # Download the update with retry mechanism
            if progress_callback:
                progress_callback(30, "下载更新", f"正在下载 {file_name}...")
            else:
                print(f"Downloading {file_name} from {download_url}...")
            
            temp_dir = tempfile.mkdtemp()
            download_path = os.path.join(temp_dir, file_name)
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
            
            # 如果是网络相关错误，显示手动更新指南
            error_str = str(e).lower()
            if any(keyword in error_str for keyword in ['connection', 'timeout', 'dns', 'network', 'github.com', 'codeload']):
                print("\n检测到网络连接问题，切换到离线模式...")
                # 尝试从缓存获取更新信息
                cached_update = self._check_offline_update()
                if cached_update and cached_update[0]:  # 如果有缓存的更新信息
                    self.show_manual_update_guide()
                else:
                    print("\n💡 网络问题解决建议:")
                    print("  - 更换DNS服务器（8.8.8.8, 114.114.114.114）")
                    print("  - 检查防火墙和杀毒软件设置")
                    print("  - 尝试使用移动热点网络")
                    print("  - 访问 https://github.com/yuanxiao9889/MJ-translate/releases 手动下载")
            
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
            skip_files = {"config.json"}
            skip_dirs = {"backup_before_update", "manual_update", ".update_cache"}
            for item in os.listdir(source_dir):
                # 跳过不应覆盖的文件/目录
                if item in skip_files or item in skip_dirs:
                    continue
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
                f"https://github.com/{repo_owner}/{repo_name}/archive/refs/tags/{tag_name}.zip"
            ],
            'manual_steps': [
                f"1. 访问发布页面: {release_data.get('html_url', '')}",
                f"2. 下载源代码ZIP文件",
                f"3. 将下载的文件放置到: {os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'manual_update')}",
                f"4. 重新运行更新程序"
            ]
        }
        
        return download_info
    
    def show_manual_update_guide(self):
        """显示手动更新指南"""
        if not self.manual_download_info:
            print("❌ 无手动更新信息可显示")
            return
        
        print("\n" + "=" * 60)
        print("🔄 手动更新指南")
        print("=" * 60)
        
        print(f"检测到新版本: {self.manual_download_info['version']}")
        print("由于网络问题，无法自动下载更新。")
        print("\n请按照以下步骤手动更新:")
        
        for step in self.manual_download_info['manual_steps']:
            print(f"  {step}")
        
        print("\n可用下载链接:")
        for i, url in enumerate(self.manual_download_info['download_urls'], 1):
            print(f"  {i}. {url}")
        
        # 检查是否已有手动下载的文件
        manual_update_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'manual_update')
        if os.path.exists(manual_update_dir):
            zip_files = [f for f in os.listdir(manual_update_dir) if f.endswith('.zip')]
            if zip_files:
                print(f"\n✓ 发现手动下载的文件: {zip_files}")
                print("重新运行更新程序以应用这些文件。")
        else:
            print(f"\n📁 请创建目录并放置下载文件: {manual_update_dir}")
        
        print("\n💡 网络问题解决建议:")
        print("  - 更换DNS服务器（8.8.8.8, 114.114.114.114）")
        print("  - 检查防火墙和杀毒软件设置")
        print("  - 尝试使用移动热点网络")
        print("  - 如在企业网络中，联系网络管理员")