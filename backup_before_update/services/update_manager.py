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
    
    def _get_proxy_config(self, test_github=False):
        """获取代理配置
        
        Args:
            test_github: 是否测试GitHub连接（用于下载时的严格测试）
        """
        user_proxies = {}
        
        # 检查环境变量中的代理配置
        if os.environ.get('HTTP_PROXY') or os.environ.get('http_proxy'):
            http_proxy = os.environ.get('HTTP_PROXY') or os.environ.get('http_proxy')
            user_proxies['http'] = http_proxy
            print(f"检测到HTTP代理: {http_proxy}")
        if os.environ.get('HTTPS_PROXY') or os.environ.get('https_proxy'):
            https_proxy = os.environ.get('HTTPS_PROXY') or os.environ.get('https_proxy')
            user_proxies['https'] = https_proxy
            print(f"检测到HTTPS代理: {https_proxy}")
        
        # 如果没有环境变量代理，尝试检测本地代理端口
        if not user_proxies:
            local_proxy_ports = ['4780', '7890', '1080', '8080']
            for port in local_proxy_ports:
                try:
                    import socket
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(1)
                    result = sock.connect_ex(('127.0.0.1', int(port)))
                    sock.close()
                    if result == 0:
                        # 测试代理是否真正可用
                        proxy_url = f'http://127.0.0.1:{port}'
                        if self._test_proxy_connectivity(proxy_url, test_github):
                            user_proxies = {'http': proxy_url, 'https': proxy_url}
                            print(f"检测到本地代理端口 {port}，使用代理: {proxy_url}")
                            break
                        else:
                            print(f"端口 {port} 可用但代理测试失败，跳过")
                except:
                    continue
        
        return user_proxies
    
    def _test_proxy_connectivity(self, proxy_url, test_github=False):
        """测试代理连通性
        
        Args:
            proxy_url: 代理URL
            test_github: 是否测试GitHub连接（用于下载时的严格测试）
        """
        try:
            import requests
            test_session = requests.Session()
            test_session.proxies = {'http': proxy_url, 'https': proxy_url}
            
            # 基本连接测试
            response = test_session.get('https://httpbin.org/ip', timeout=5)
            if response.status_code != 200:
                return False
            
            # 如果需要测试GitHub连接（下载时使用）
            if test_github:
                response = test_session.get('https://api.github.com', timeout=10)
                return response.status_code == 200
            
            return True
        except:
            return False

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
        
        # 获取代理配置（不进行GitHub严格测试）
        user_proxies = self._get_proxy_config(test_github=False)
        
        # 重试机制
        max_retries = 3
        for attempt in range(max_retries):
            try:
                print(f"正在检查更新... (尝试 {attempt + 1}/{max_retries})")
                response = session.get(
                    api_url, 
                    headers=headers,
                    timeout=30,  # 30秒超时
                    proxies=user_proxies  # 使用检测到的代理配置
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

    def _save_release_info(self, latest_release):
        """保存发布信息到缓存文件供离线使用"""
        try:
            cache_dir = Path(__file__).parent.parent / '.update_cache'
            cache_dir.mkdir(exist_ok=True)
            cache_file = cache_dir / 'latest_release.json'
            
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(latest_release, f, ensure_ascii=False, indent=2)
            
            print(f"发布信息已缓存到: {cache_file}")
        except Exception as e:
            print(f"警告: 保存发布信息失败: {e}")
    
    def is_new_version_available(self, latest_version):
        """检查是否有新版本可用
        
        Args:
            latest_version (str): 最新版本号
            
        Returns:
            bool: 如果有新版本可用返回True，否则返回False
        """
        try:
            # 清理版本号，移除'v'前缀
            current = self.current_version.lstrip('v')
            latest = latest_version.lstrip('v')
            
            # 使用semver进行版本比较
            return semver.compare(latest, current) > 0
        except Exception as e:
            print(f"版本比较失败: {e}")
            # 如果版本比较失败，进行简单的字符串比较作为后备
            return latest_version != self.current_version
    
    def _get_download_url_with_fallback(self, latest_release):
        """从GitHub release获取下载URL，支持多种下载源
        
        Args:
            latest_release (dict): GitHub API返回的release信息
            
        Returns:
            tuple: (download_url, file_name, file_size)
        """
        try:
            # 优先使用assets中的文件
            assets = latest_release.get('assets', [])
            if assets:
                # 查找zip文件
                for asset in assets:
                    if asset['name'].endswith('.zip'):
                        return (
                            asset['browser_download_url'],
                            asset['name'],
                            asset.get('size', 0)
                        )
                
                # 如果没有zip文件，使用第一个asset
                first_asset = assets[0]
                return (
                    first_asset['browser_download_url'],
                    first_asset['name'],
                    first_asset.get('size', 0)
                )
            
            # 如果没有assets，使用源码下载链接
            tag_name = latest_release.get('tag_name', '')
            if tag_name:
                repo_owner = self.config.get('github_owner')
                repo_name = self.config.get('github_repo')
                if repo_owner and repo_name:
                    # 使用codeload下载源码zip
                    download_url = f"https://codeload.github.com/{repo_owner}/{repo_name}/zip/refs/tags/{tag_name}"
                    file_name = f"{repo_name}-{tag_name.lstrip('v')}.zip"
                    return (download_url, file_name, 0)  # 源码下载无法预知大小
            
            # 如果都失败了，抛出异常
            raise Exception("GitHub Release中没有找到可下载的文件")
            
        except Exception as e:
            print(f"获取下载URL失败: {e}")
            raise Exception(f"GitHub Release中没有找到可下载的文件: {e}")

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
            user_proxies = self._get_proxy_config(test_github=False)
            session = requests.Session()
            if user_proxies:
                session.proxies = user_proxies
            headers = {
                'User-Agent': 'MJ-Translator-Update-Checker/1.0',
                'Accept': 'application/vnd.github.v3+json'
            }
            
            # Get latest release info
            if progress_callback:
                progress_callback(5, "获取更新信息", "正在连接GitHub API...")
            response = session.get(api_url, headers=headers, timeout=30, proxies=user_proxies if user_proxies else {})
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
    
    def _rollback_update(self, backup_dir):
        """从备份目录恢复文件
        
        Args:
            backup_dir (Path): 备份目录路径
        """
        try:
            project_root = Path(__file__).parent.parent
            print(f"开始回滚更新，从备份目录恢复文件: {backup_dir}")
            
            # 需要恢复的文件和目录
            backup_items = [
                'main.py',
                'services/',
                'views/',
                'config.json',
                'requirements.txt'
            ]
            
            for item in backup_items:
                backup_path = backup_dir / item
                target_path = project_root / item
                
                if backup_path.exists():
                    try:
                        if backup_path.is_file():
                            # 恢复文件
                            if target_path.exists():
                                target_path.unlink()  # 删除当前文件
                            shutil.copy2(backup_path, target_path)
                            print(f"已恢复文件: {item}")
                        elif backup_path.is_dir():
                            # 恢复目录
                            if target_path.exists():
                                shutil.rmtree(target_path)  # 删除当前目录
                            shutil.copytree(backup_path, target_path)
                            print(f"已恢复目录: {item}")
                    except Exception as e:
                        print(f"恢复 {item} 时出错: {e}")
                        continue
                else:
                    print(f"备份中未找到: {item}")
            
            print("回滚完成")
            
        except Exception as e:
             print(f"回滚过程中发生错误: {e}")
             raise
    
    def _extract_and_apply_update(self, download_path, project_root):
        """解压并应用更新文件
        
        Args:
            download_path (str): 下载的zip文件路径
            project_root (Path): 项目根目录
        """
        try:
            print(f"开始解压更新文件: {download_path}")
            
            # 创建临时解压目录
            extract_dir = tempfile.mkdtemp()
            
            try:
                # 解压zip文件
                with zipfile.ZipFile(download_path, 'r') as zip_ref:
                    zip_ref.extractall(extract_dir)
                
                print(f"文件已解压到: {extract_dir}")
                
                # 查找解压后的内容
                extracted_items = os.listdir(extract_dir)
                if len(extracted_items) == 1 and os.path.isdir(os.path.join(extract_dir, extracted_items[0])):
                    # 如果只有一个目录，说明是GitHub的源码包格式
                    source_dir = os.path.join(extract_dir, extracted_items[0])
                else:
                    # 直接使用解压目录
                    source_dir = extract_dir
                
                print(f"源文件目录: {source_dir}")
                
                # 需要更新的文件和目录
                update_items = [
                    'main.py',
                    'services/',
                    'views/',
                    'requirements.txt'
                ]
                
                # 应用更新
                for item in update_items:
                    source_path = os.path.join(source_dir, item)
                    target_path = project_root / item
                    
                    if os.path.exists(source_path):
                        try:
                            if os.path.isfile(source_path):
                                # 更新文件
                                if target_path.exists():
                                    target_path.unlink()
                                shutil.copy2(source_path, target_path)
                                print(f"已更新文件: {item}")
                            elif os.path.isdir(source_path):
                                # 更新目录
                                if target_path.exists():
                                    shutil.rmtree(target_path)
                                shutil.copytree(source_path, target_path)
                                print(f"已更新目录: {item}")
                        except Exception as e:
                            print(f"更新 {item} 时出错: {e}")
                            raise
                    else:
                        print(f"更新包中未找到: {item}")
                
                print("更新应用完成")
                
            finally:
                # 清理临时解压目录
                if os.path.exists(extract_dir):
                    shutil.rmtree(extract_dir, ignore_errors=True)
                    
        except Exception as e:
             print(f"解压和应用更新时发生错误: {e}")
             raise
    
    def _download_with_retry(self, download_url, download_path, headers, max_retries=3):
        """带重试机制的文件下载
        
        Args:
            download_url (str): 下载URL
            download_path (str): 本地保存路径
            headers (dict): HTTP请求头
            max_retries (int): 最大重试次数
        """
        user_proxies = self._get_proxy_config(test_github=True)
        
        for attempt in range(max_retries):
            try:
                print(f"开始下载 (尝试 {attempt + 1}/{max_retries}): {download_url}")
                
                session = requests.Session()
                if user_proxies:
                    session.proxies = user_proxies
                
                # 使用流式下载以支持大文件
                response = session.get(
                    download_url, 
                    headers=headers, 
                    stream=True, 
                    timeout=60,
                    proxies=user_proxies if user_proxies else {}
                )
                response.raise_for_status()
                
                # 获取文件大小
                total_size = int(response.headers.get('content-length', 0))
                downloaded_size = 0
                
                # 写入文件
                with open(download_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded_size += len(chunk)
                            
                            # 显示下载进度
                            if total_size > 0:
                                progress = (downloaded_size / total_size) * 100
                                print(f"\r下载进度: {progress:.1f}% ({downloaded_size}/{total_size} bytes)", end='', flush=True)
                
                print(f"\n下载完成: {download_path}")
                
                # 验证下载的文件
                if os.path.exists(download_path) and os.path.getsize(download_path) > 0:
                    print(f"文件验证成功，大小: {os.path.getsize(download_path)} bytes")
                    return
                else:
                    raise Exception("下载的文件为空或不存在")
                    
            except Exception as e:
                print(f"\n下载尝试 {attempt + 1} 失败: {e}")
                
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2  # 递增等待时间
                    print(f"等待 {wait_time} 秒后重试...")
                    time.sleep(wait_time)
                else:
                     print("所有下载尝试都失败了")
                     raise Exception(f"下载失败，已重试 {max_retries} 次: {e}")
    
    def _cleanup_after_update(self, temp_files=None, backup_dir=None, keep_backup=True):
        """更新后的清理工作
        
        Args:
            temp_files (list): 需要清理的临时文件列表
            backup_dir (str): 备份目录路径
            keep_backup (bool): 是否保留备份
        """
        try:
            # 清理临时文件
            if temp_files:
                for temp_file in temp_files:
                    if temp_file and os.path.exists(temp_file):
                        try:
                            if os.path.isfile(temp_file):
                                os.remove(temp_file)
                                print(f"已删除临时文件: {temp_file}")
                            elif os.path.isdir(temp_file):
                                shutil.rmtree(temp_file, ignore_errors=True)
                                print(f"已删除临时目录: {temp_file}")
                        except Exception as e:
                            print(f"清理临时文件失败 {temp_file}: {e}")
            
            # 处理备份目录
            if backup_dir and os.path.exists(backup_dir):
                if not keep_backup:
                    try:
                        shutil.rmtree(backup_dir, ignore_errors=True)
                        print(f"已删除备份目录: {backup_dir}")
                    except Exception as e:
                        print(f"删除备份目录失败: {e}")
                else:
                    print(f"备份已保留在: {backup_dir}")
                    
                    # 清理旧备份（保留最近的3个）
                    try:
                        backup_parent = os.path.dirname(backup_dir)
                        if os.path.exists(backup_parent):
                            backup_dirs = []
                            for item in os.listdir(backup_parent):
                                item_path = os.path.join(backup_parent, item)
                                if os.path.isdir(item_path) and item.startswith('backup_'):
                                    backup_dirs.append((item_path, os.path.getctime(item_path)))
                            
                            # 按创建时间排序，保留最新的3个
                            backup_dirs.sort(key=lambda x: x[1], reverse=True)
                            for old_backup, _ in backup_dirs[3:]:
                                try:
                                    shutil.rmtree(old_backup, ignore_errors=True)
                                    print(f"已清理旧备份: {old_backup}")
                                except Exception as e:
                                    print(f"清理旧备份失败 {old_backup}: {e}")
                    except Exception as e:
                        print(f"清理旧备份时发生错误: {e}")
            
            # 清理下载缓存目录
            cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'cache')
            if os.path.exists(cache_dir):
                try:
                    for item in os.listdir(cache_dir):
                        item_path = os.path.join(cache_dir, item)
                        if item.endswith(('.zip', '.tar.gz', '.tmp')):
                            try:
                                if os.path.isfile(item_path):
                                    # 检查文件年龄，删除超过1天的缓存文件
                                    if time.time() - os.path.getctime(item_path) > 86400:  # 24小时
                                        os.remove(item_path)
                                        print(f"已清理缓存文件: {item_path}")
                            except Exception as e:
                                print(f"清理缓存文件失败 {item_path}: {e}")
                except Exception as e:
                    print(f"清理缓存目录时发生错误: {e}")
            
            print("更新后清理完成")
            
        except Exception as e:
             print(f"清理过程中发生错误: {e}")
             # 清理失败不应该影响更新流程，所以不抛出异常
    
    def _release_file_locks(self, file_paths=None):
        """释放文件句柄
        
        Args:
            file_paths (list): 需要释放句柄的文件路径列表
        """
        try:
            import gc
            import sys
            
            # 强制垃圾回收，释放可能的文件句柄
            gc.collect()
            
            # 如果指定了文件路径，尝试关闭相关的文件句柄
            if file_paths:
                for file_path in file_paths:
                    if file_path:
                        try:
                            # 检查文件是否被当前进程占用
                            if os.path.exists(file_path):
                                # 尝试以独占模式打开文件来测试是否被占用
                                try:
                                    with open(file_path, 'r+b') as test_file:
                                        pass
                                    print(f"文件句柄已释放: {file_path}")
                                except (IOError, OSError) as e:
                                    if "being used by another process" in str(e).lower():
                                        print(f"文件仍被占用: {file_path}")
                                        # 在Windows上，可以尝试等待一段时间
                                        if sys.platform.startswith('win'):
                                            time.sleep(0.5)
                                            try:
                                                with open(file_path, 'r+b') as test_file:
                                                    pass
                                                print(f"延迟后文件句柄已释放: {file_path}")
                                            except (IOError, OSError):
                                                print(f"文件句柄释放失败: {file_path}")
                                    else:
                                        print(f"文件访问测试失败: {file_path} - {e}")
                        except Exception as e:
                            print(f"释放文件句柄时发生错误 {file_path}: {e}")
            
            # 通用的文件句柄释放操作
            try:
                # 关闭所有打开的文件描述符（除了标准输入输出错误）
                import resource
                if hasattr(resource, 'getrlimit'):
                    max_fd = resource.getrlimit(resource.RLIMIT_NOFILE)[0]
                    for fd in range(3, min(max_fd, 256)):  # 限制检查范围避免性能问题
                        try:
                            os.close(fd)
                        except (OSError, ValueError):
                            pass  # 文件描述符可能已经关闭或无效
            except (ImportError, AttributeError):
                # resource模块在Windows上可能不可用
                pass
            
            # 再次强制垃圾回收
            gc.collect()
            
            print("文件句柄释放操作完成")
            
        except Exception as e:
             print(f"释放文件句柄时发生错误: {e}")
             # 句柄释放失败不应该影响主流程
    
    def _save_installed_version(self, version):
        """保存已安装版本号
        
        Args:
            version (str): 版本号
        """
        try:
            version_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'version.txt')
            
            # 确保目录存在
            os.makedirs(os.path.dirname(version_file), exist_ok=True)
            
            # 保存版本信息
            version_info = {
                'version': version,
                'install_time': time.strftime('%Y-%m-%d %H:%M:%S'),
                'install_timestamp': int(time.time())
            }
            
            # 写入版本文件
            with open(version_file, 'w', encoding='utf-8') as f:
                json.dump(version_info, f, indent=2, ensure_ascii=False)
            
            print(f"版本信息已保存: {version} (时间: {version_info['install_time']})")
            
            # 同时更新配置文件中的版本信息（如果存在）
            try:
                config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'config.json')
                if os.path.exists(config_file):
                    with open(config_file, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                    
                    # 更新版本信息
                    if 'app_info' not in config:
                        config['app_info'] = {}
                    
                    config['app_info']['version'] = version
                    config['app_info']['last_update'] = version_info['install_time']
                    
                    # 写回配置文件
                    with open(config_file, 'w', encoding='utf-8') as f:
                        json.dump(config, f, indent=2, ensure_ascii=False)
                    
                    print(f"配置文件中的版本信息已更新")
                    
            except Exception as e:
                print(f"更新配置文件版本信息时发生错误: {e}")
            
            # 更新内存中的版本信息
            self.current_version = version
            
        except Exception as e:
            print(f"保存版本信息时发生错误: {e}")
            raise Exception(f"无法保存版本信息: {e}")
