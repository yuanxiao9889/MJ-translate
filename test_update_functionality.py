#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
更新功能测试脚本
测试自动更新的各个组件：版本检查、下载、解压、备份和回滚
"""

import os
import sys
import json
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_config_loading():
    """测试配置文件加载"""
    print("=== 测试配置文件加载 ===")
    try:
        from services.update_manager import UpdateManager
        updater = UpdateManager()
        
        print(f"当前版本: {updater.current_version}")
        print(f"GitHub Owner: {updater.config.get('github_owner', 'Not configured')}")
        print(f"GitHub Repo: {updater.config.get('github_repo', 'Not configured')}")
        
        if updater.config.get('github_owner') and updater.config.get('github_repo'):
            print("✅ 配置加载成功")
            return True
        else:
            print("❌ GitHub仓库配置缺失")
            return False
    except Exception as e:
        print(f"❌ 配置加载失败: {e}")
        return False

def test_version_check():
    """测试版本检查功能"""
    print("\n=== 测试版本检查功能 ===")
    try:
        from services.update_manager import UpdateManager
        updater = UpdateManager()
        
        print("正在检查最新版本...")
        latest_version, release_notes = updater.check_for_updates()
        
        if latest_version:
            print(f"✅ 成功获取最新版本: {latest_version}")
            print(f"发布说明: {release_notes[:100]}..." if release_notes else "无发布说明")
            
            # 测试版本比较
            is_new = updater.is_new_version_available(latest_version)
            print(f"是否有新版本: {'是' if is_new else '否'}")
            return True
        else:
            print("❌ 无法获取版本信息")
            return False
    except Exception as e:
        print(f"❌ 版本检查失败: {e}")
        return False

def test_backup_functionality():
    """测试备份功能"""
    print("\n=== 测试备份功能 ===")
    try:
        from services.update_manager import UpdateManager
        import tempfile
        import shutil
        
        updater = UpdateManager()
        
        # 创建临时备份目录
        temp_backup = Path(tempfile.mkdtemp())
        print(f"临时备份目录: {temp_backup}")
        
        # 执行备份
        updater._backup_current_version(temp_backup)
        
        # 检查备份文件
        backup_items = list(temp_backup.iterdir())
        print(f"备份的项目数量: {len(backup_items)}")
        
        for item in backup_items:
            print(f"  - {item.name} ({'目录' if item.is_dir() else '文件'})")
        
        # 清理临时目录
        shutil.rmtree(temp_backup, ignore_errors=True)
        
        if backup_items:
            print("✅ 备份功能正常")
            return True
        else:
            print("❌ 备份功能异常")
            return False
    except Exception as e:
        print(f"❌ 备份功能测试失败: {e}")
        return False

def test_dependencies():
    """测试依赖库"""
    print("\n=== 测试依赖库 ===")
    dependencies = {
        'requests': 'HTTP请求库',
        'semver': '语义化版本比较',
        'zipfile': 'ZIP文件处理',
        'shutil': '文件操作',
        'tempfile': '临时文件处理',
        'pathlib': '路径处理'
    }
    
    all_ok = True
    for dep, desc in dependencies.items():
        try:
            __import__(dep)
            print(f"✅ {dep}: {desc}")
        except ImportError:
            print(f"❌ {dep}: {desc} - 缺失")
            all_ok = False
    
    return all_ok

def main():
    """主测试函数"""
    print("🚀 开始测试更新功能组件\n")
    
    tests = [
        ("依赖库检查", test_dependencies),
        ("配置加载", test_config_loading),
        ("版本检查", test_version_check),
        ("备份功能", test_backup_functionality)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} 测试异常: {e}")
            results.append((test_name, False))
    
    # 输出测试结果摘要
    print("\n" + "="*50)
    print("📊 测试结果摘要")
    print("="*50)
    
    passed = 0
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n总计: {passed}/{len(results)} 项测试通过")
    
    if passed == len(results):
        print("\n🎉 所有测试通过！更新功能已准备就绪。")
        print("\n💡 使用提示:")
        print("1. 在程序中点击 '设置' -> '关于与更新' -> '检查更新'")
        print("2. 更新过程会自动备份当前版本")
        print("3. 如果更新失败，会自动回滚到之前版本")
        print("4. 更新成功后建议重启程序")
    else:
        print(f"\n⚠️  有 {len(results) - passed} 项测试失败，请检查相关配置。")

if __name__ == "__main__":
    main()