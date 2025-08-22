#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitHub Repository Synchronization Script

This script performs the following operations:
1. Clone GitHub repository to current directory
2. Compare local files with GitHub repository files
3. Automatically overwrite local versions with GitHub versions for inconsistent files
4. Move local files that don't exist in GitHub repository to a "deprecated" folder

Features:
- Support for specifying GitHub repository URL and local target path
- Use Git commands for repository cloning and file comparison
- File difference detection mechanism
- Automatic creation of deprecated folder (if not exists)
- Operation logging output
- Error handling mechanism
"""

import os
import sys
import shutil
import subprocess
import argparse
import logging
import tempfile
from pathlib import Path
from typing import Set, List, Tuple
import hashlib
import json
from datetime import datetime


class RepoSyncLogger:
    """日志管理器"""
    
    def __init__(self, log_file: str = "repo_sync.log"):
        self.logger = logging.getLogger("RepoSync")
        self.logger.setLevel(logging.INFO)
        
        # 创建文件处理器
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        
        # 创建控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # 创建格式器
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        # 添加处理器
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
    
    def info(self, message: str):
        self.logger.info(message)
    
    def error(self, message: str):
        self.logger.error(message)
    
    def warning(self, message: str):
        self.logger.warning(message)


class GitRepoSync:
    """GitHub仓库同步器"""
    
    def __init__(self, repo_url: str, target_path: str, logger: RepoSyncLogger):
        self.repo_url = repo_url
        self.target_path = Path(target_path).resolve()
        self.logger = logger
        self.temp_repo_path = None
        self.deprecated_folder = self.target_path / "deprecated"
        
        # 忽略的文件和文件夹
        self.ignore_patterns = {
            '.git', '__pycache__', '.pyc', '.pyo', '.pyd',
            'node_modules', '.env', '.venv', 'venv',
            '.DS_Store', 'Thumbs.db', '*.log'
        }
    
    def run_git_command(self, cmd: List[str], cwd: str = None) -> Tuple[bool, str]:
        """执行Git命令"""
        try:
            result = subprocess.run(
                cmd, 
                cwd=cwd, 
                capture_output=True, 
                text=True, 
                encoding='utf-8'
            )
            if result.returncode == 0:
                return True, result.stdout.strip()
            else:
                return False, result.stderr.strip()
        except Exception as e:
            return False, str(e)
    
    def check_git_available(self) -> bool:
        """检查Git是否可用"""
        success, output = self.run_git_command(['git', '--version'])
        if success:
            self.logger.info(f"Git版本: {output}")
            return True
        else:
            self.logger.error("Git未安装或不可用")
            return False
    
    def clone_repository(self) -> bool:
        """克隆仓库到临时目录"""
        try:
            # 创建临时目录
            self.temp_repo_path = Path(tempfile.mkdtemp(prefix="repo_sync_"))
            self.logger.info(f"创建临时目录: {self.temp_repo_path}")
            
            # 克隆仓库
            self.logger.info(f"正在克隆仓库: {self.repo_url}")
            success, output = self.run_git_command([
                'git', 'clone', self.repo_url, str(self.temp_repo_path)
            ])
            
            if success:
                self.logger.info("仓库克隆成功")
                return True
            else:
                self.logger.error(f"仓库克隆失败: {output}")
                return False
                
        except Exception as e:
            self.logger.error(f"克隆仓库时发生错误: {str(e)}")
            return False
    
    def get_file_hash(self, file_path: Path) -> str:
        """计算文件MD5哈希值"""
        try:
            hash_md5 = hashlib.md5()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception:
            return ""
    
    def should_ignore(self, path: Path) -> bool:
        """检查文件是否应该被忽略"""
        path_str = str(path)
        for pattern in self.ignore_patterns:
            if pattern in path_str or path.name.startswith('.'):
                return True
        return False
    
    def get_all_files(self, root_path: Path) -> Set[Path]:
        """获取目录下所有文件的相对路径"""
        files = set()
        try:
            for file_path in root_path.rglob('*'):
                if file_path.is_file() and not self.should_ignore(file_path):
                    relative_path = file_path.relative_to(root_path)
                    files.add(relative_path)
        except Exception as e:
            self.logger.error(f"获取文件列表时发生错误: {str(e)}")
        return files
    
    def compare_files(self) -> Tuple[Set[Path], Set[Path], Set[Path]]:
        """对比本地文件与仓库文件
        
        Returns:
            Tuple[Set[Path], Set[Path], Set[Path]]: 
            (需要更新的文件, 需要删除的文件, 新增的文件)
        """
        if not self.temp_repo_path:
            return set(), set(), set()
        
        self.logger.info("正在对比文件差异...")
        
        # 获取仓库文件列表
        repo_files = self.get_all_files(self.temp_repo_path)
        
        # 获取本地文件列表
        local_files = self.get_all_files(self.target_path)
        
        # 需要更新的文件（内容不同）
        files_to_update = set()
        
        # 需要删除的文件（本地有但仓库没有）
        files_to_deprecate = local_files - repo_files
        
        # 新增的文件（仓库有但本地没有）
        files_to_add = repo_files - local_files
        
        # 检查共同文件的内容差异
        common_files = repo_files & local_files
        for file_path in common_files:
            repo_file = self.temp_repo_path / file_path
            local_file = self.target_path / file_path
            
            if local_file.exists() and repo_file.exists():
                repo_hash = self.get_file_hash(repo_file)
                local_hash = self.get_file_hash(local_file)
                
                if repo_hash != local_hash and repo_hash and local_hash:
                    files_to_update.add(file_path)
        
        self.logger.info(f"发现 {len(files_to_update)} 个文件需要更新")
        self.logger.info(f"发现 {len(files_to_deprecate)} 个文件需要废弃")
        self.logger.info(f"发现 {len(files_to_add)} 个新文件")
        
        return files_to_update, files_to_deprecate, files_to_add
    
    def create_deprecated_folder(self) -> bool:
        """创建废弃文件夹"""
        try:
            if not self.deprecated_folder.exists():
                self.deprecated_folder.mkdir(parents=True, exist_ok=True)
                self.logger.info(f"创建废弃文件夹: {self.deprecated_folder}")
            return True
        except Exception as e:
            self.logger.error(f"创建废弃文件夹失败: {str(e)}")
            return False
    
    def move_to_deprecated(self, files_to_deprecate: Set[Path]) -> bool:
        """将废弃文件移动到deprecated文件夹"""
        if not files_to_deprecate:
            return True
        
        if not self.create_deprecated_folder():
            return False
        
        success_count = 0
        for file_path in files_to_deprecate:
            try:
                source_file = self.target_path / file_path
                if not source_file.exists():
                    continue
                
                # 创建目标目录结构
                target_file = self.deprecated_folder / file_path
                target_file.parent.mkdir(parents=True, exist_ok=True)
                
                # 如果目标文件已存在，添加时间戳
                if target_file.exists():
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    name_parts = target_file.name.split('.')
                    if len(name_parts) > 1:
                        new_name = f"{'.'.join(name_parts[:-1])}_{timestamp}.{name_parts[-1]}"
                    else:
                        new_name = f"{target_file.name}_{timestamp}"
                    target_file = target_file.parent / new_name
                
                # 移动文件
                shutil.move(str(source_file), str(target_file))
                self.logger.info(f"移动文件到废弃文件夹: {file_path} -> {target_file.relative_to(self.target_path)}")
                success_count += 1
                
            except Exception as e:
                self.logger.error(f"移动文件失败 {file_path}: {str(e)}")
        
        self.logger.info(f"成功移动 {success_count}/{len(files_to_deprecate)} 个文件到废弃文件夹")
        return success_count == len(files_to_deprecate)
    
    def update_files(self, files_to_update: Set[Path], files_to_add: Set[Path]) -> bool:
        """更新和添加文件"""
        all_files = files_to_update | files_to_add
        if not all_files:
            return True
        
        success_count = 0
        for file_path in all_files:
            try:
                source_file = self.temp_repo_path / file_path
                target_file = self.target_path / file_path
                
                if not source_file.exists():
                    continue
                
                # 创建目标目录
                target_file.parent.mkdir(parents=True, exist_ok=True)
                
                # 复制文件
                shutil.copy2(str(source_file), str(target_file))
                
                action = "更新" if file_path in files_to_update else "添加"
                self.logger.info(f"{action}文件: {file_path}")
                success_count += 1
                
            except Exception as e:
                self.logger.error(f"处理文件失败 {file_path}: {str(e)}")
        
        self.logger.info(f"成功处理 {success_count}/{len(all_files)} 个文件")
        return success_count == len(all_files)
    
    def cleanup_temp_directory(self):
        """清理临时目录"""
        if self.temp_repo_path and self.temp_repo_path.exists():
            try:
                shutil.rmtree(str(self.temp_repo_path))
                self.logger.info(f"清理临时目录: {self.temp_repo_path}")
            except Exception as e:
                self.logger.error(f"清理临时目录失败: {str(e)}")
    
    def generate_sync_report(self, files_to_update: Set[Path], 
                           files_to_deprecate: Set[Path], 
                           files_to_add: Set[Path]) -> str:
        """生成同步报告"""
        report = {
            "timestamp": datetime.now().isoformat(),
            "repository": self.repo_url,
            "target_path": str(self.target_path),
            "summary": {
                "updated_files": len(files_to_update),
                "deprecated_files": len(files_to_deprecate),
                "added_files": len(files_to_add)
            },
            "details": {
                "updated_files": [str(f) for f in files_to_update],
                "deprecated_files": [str(f) for f in files_to_deprecate],
                "added_files": [str(f) for f in files_to_add]
            }
        }
        
        report_file = self.target_path / "sync_report.json"
        try:
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            self.logger.info(f"同步报告已保存: {report_file}")
            return str(report_file)
        except Exception as e:
            self.logger.error(f"保存同步报告失败: {str(e)}")
            return ""
    
    def sync(self) -> bool:
        """执行完整的同步流程"""
        try:
            self.logger.info("开始仓库同步流程")
            
            # 检查Git可用性
            if not self.check_git_available():
                return False
            
            # 克隆仓库
            if not self.clone_repository():
                return False
            
            # 对比文件
            files_to_update, files_to_deprecate, files_to_add = self.compare_files()
            
            # 移动废弃文件
            if not self.move_to_deprecated(files_to_deprecate):
                self.logger.warning("部分文件移动到废弃文件夹失败")
            
            # 更新和添加文件
            if not self.update_files(files_to_update, files_to_add):
                self.logger.warning("部分文件更新失败")
            
            # 生成同步报告
            self.generate_sync_report(files_to_update, files_to_deprecate, files_to_add)
            
            self.logger.info("仓库同步完成")
            return True
            
        except Exception as e:
            self.logger.error(f"同步过程中发生错误: {str(e)}")
            return False
        finally:
            # 清理临时目录
            self.cleanup_temp_directory()


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="GitHub仓库同步工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  python repo_sync.py -r https://github.com/user/repo.git
  python repo_sync.py -r https://github.com/user/repo.git -t /path/to/target
  python repo_sync.py -r https://github.com/user/repo.git -t . --log sync.log
        """
    )
    
    parser.add_argument(
        '-r', '--repository',
        required=True,
        help='GitHub仓库URL'
    )
    
    parser.add_argument(
        '-t', '--target',
        default='.',
        help='本地目标路径 (默认: 当前目录)'
    )
    
    parser.add_argument(
        '--log',
        default='repo_sync.log',
        help='日志文件路径 (默认: repo_sync.log)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='仅显示将要执行的操作，不实际执行'
    )
    
    args = parser.parse_args()
    
    # 初始化日志器
    logger = RepoSyncLogger(args.log)
    
    try:
        # 创建同步器
        syncer = GitRepoSync(args.repository, args.target, logger)
        
        if args.dry_run:
            logger.info("DRY RUN模式 - 仅显示操作，不实际执行")
            # 在dry-run模式下，只执行到文件对比阶段
            if syncer.check_git_available() and syncer.clone_repository():
                files_to_update, files_to_deprecate, files_to_add = syncer.compare_files()
                logger.info("DRY RUN完成 - 实际操作需要移除--dry-run参数")
            syncer.cleanup_temp_directory()
        else:
            # 执行同步
            success = syncer.sync()
            sys.exit(0 if success else 1)
            
    except KeyboardInterrupt:
        logger.info("用户中断操作")
        sys.exit(1)
    except Exception as e:
        logger.error(f"程序执行失败: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()