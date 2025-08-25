import requests
import semver
import json
import os
import zipfile
import shutil
import tempfile
from pathlib import Path
from services import __version__ as current_version
import stat
import ctypes
import gc
import time

class UpdateManager:
    def __init__(self):
        self.config = self._load_config()
        # 优先从本地安装版本文件读取，若不存在则回退到打包内的 __version__
        try:
            self.current_version = self._load_installed_version() or current_version
        except Exception:
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

    def _load_installed_version(self) -> str:
        """从项目根目录读取已安装版本号（installed_version.txt）。
        若文件不存在则返回空字符串，调用方需做回退处理。
        """
        try:
            project_root = Path(__file__).parent.parent
            ver_file = project_root / 'installed_version.txt'
            if ver_file.exists():
                return ver_file.read_text(encoding='utf-8').strip()
        except Exception:
            pass
        return ""

    def _save_release_info(self, release_data):
        """保存发布信息到本地缓存供离线使用"""
        try:
            cache_dir = Path(__file__).parent.parent / '.update_cache'
            cache_dir.mkdir(exist_ok=True)
            cache_file = cache_dir / 'latest_release.json'
            
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(release_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"警告: 保存发布信息缓存失败: {e}")

    def _save_installed_version(self, version: str) -> None:
        """将已安装版本号写入项目根目录的 installed_version.txt 以供主程序显示。"""
        try:
            if not version:
                return
            project_root = Path(__file__).parent.parent
            ver_file = project_root / 'installed_version.txt'
            ver_file.write_text(version.strip(), encoding='utf-8')
        except Exception as e:
            print(f"警告: 写入已安装版本失败: {e}")

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
                
            # 在应用更新之前尽可能释放日志文件句柄，避免 Windows 下文件占用
            self._release_file_locks()
            
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

            # 记录已安装版本，供主程序显示（无需重启即可读取到新版本号）
            try:
                new_ver = str(latest_release.get('tag_name', '')).lstrip('v')
                if new_ver:
                    self._save_installed_version(new_ver)
                    self.current_version = new_ver
            except Exception as e:
                print(f"警告: 更新版本号持久化失败: {e}")
            
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

    def _check_offline_update(self):
        """检查离线缓存的更新信息"""
        try:
            cache_dir = Path(__file__).parent.parent / '.update_cache'
            cache_file = cache_dir / 'latest_release.json'
            
            if cache_file.exists():
                with open(cache_file, 'r', encoding='utf-8') as f:
                    release_data = json.load(f)
                
                latest_version = release_data.get('tag_name', '').lstrip('v')
                if latest_version and semver.compare(latest_version, self.current_version) > 0:
                    return True, latest_version, release_data.get('body', ''), release_data.get('html_url', '')
            
            return False, self.current_version, '', ''
        except Exception as e:
            print(f"检查离线更新缓存失败: {e}")
            return False, self.current_version, '', ''

    def _get_download_url_with_fallback(self, release_data):
        """获取下载URL，支持多种下载源"""
        assets = release_data.get('assets', [])
        
        # 查找zip文件
        for asset in assets:
            if asset['name'].endswith('.zip'):
                return asset['browser_download_url'], asset['name'], asset.get('size', 0)
        
        # 如果没有找到assets，使用源码下载
        tag_name = release_data.get('tag_name', 'main')
        repo_owner = self.config.get('github_owner', 'yuanxiao9889')
        repo_name = self.config.get('github_repo', 'MJ-translate')
        
        download_url = f"https://github.com/{repo_owner}/{repo_name}/archive/refs/tags/{tag_name}.zip"
        file_name = f"{repo_name}-{tag_name.lstrip('v')}.zip"
        
        return download_url, file_name, 0

    def _download_with_retry(self, url, download_path, headers, max_retries=3):
        """带重试机制的下载"""
        session = requests.Session()
        session.trust_env = False
        session.proxies = {}
        
        for attempt in range(max_retries):
            try:
                response = session.get(url, headers=headers, timeout=60, stream=True, proxies={})
                response.raise_for_status()
                
                with open(download_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                
                print(f"下载完成: {download_path}")
                return
                
            except Exception as e:
                print(f"下载失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    print("正在重试...")
                    time.sleep(2)
                else:
                    raise

    def _release_file_locks(self):
        """释放文件锁定，避免Windows下文件占用问题"""
        try:
            gc.collect()
            time.sleep(0.5)
        except Exception:
            pass

    def _extract_and_apply_update(self, zip_path, project_root):
        """解压并应用更新"""
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            # 获取zip文件中的根目录名
            names = zip_ref.namelist()
            if names:
                root_folder = names[0].split('/')[0]
                
                # 解压到临时目录
                temp_extract_dir = tempfile.mkdtemp()
                zip_ref.extractall(temp_extract_dir)
                
                # 复制文件到项目根目录
                source_dir = Path(temp_extract_dir) / root_folder
                if source_dir.exists():
                    self._copy_update_files(source_dir, project_root)
                
                # 清理临时解压目录
                shutil.rmtree(temp_extract_dir, ignore_errors=True)

    def _copy_update_files(self, source_dir, dest_dir):
        """复制更新文件到目标目录"""
        for item in source_dir.rglob('*'):
            if item.is_file():
                rel_path = item.relative_to(source_dir)
                dest_path = dest_dir / rel_path
                
                # 创建目标目录
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                
                # 复制文件
                try:
                    shutil.copy2(item, dest_path)
                except PermissionError:
                    # 如果文件被占用，尝试修改权限后再复制
                    try:
                        os.chmod(dest_path, stat.S_IWRITE)
                        shutil.copy2(item, dest_path)
                    except Exception as e:
                        print(f"警告: 无法更新文件 {dest_path}: {e}")

    def _cleanup_after_update(self, backup_dir, temp_dir):
        """更新后清理临时文件"""
        try:
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception as e:
            print(f"清理临时文件失败: {e}")

    def _rollback_update(self, backup_dir):
        """回滚更新"""
        try:
            project_root = Path(__file__).parent.parent
            
            for item in backup_dir.rglob('*'):
                if item.is_file():
                    rel_path = item.relative_to(backup_dir)
                    dest_path = project_root / rel_path
                    
                    dest_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(item, dest_path)
                    
        except Exception as e:
            print(f"回滚失败: {e}")

    def show_manual_update_guide(self):
        """显示手动更新指南"""
        print("\n📋 手动更新指南:")
        print("1. 访问: https://github.com/yuanxiao9889/MJ-translate/releases")
        print("2. 下载最新版本的zip文件")
        print("3. 解压并替换当前程序文件")
        print("4. 重启程序")
