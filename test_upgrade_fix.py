#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
升级功能修复测试脚本
"""

import os
import sys
from services.update_manager import UpdateManager
from services import __version__ as current_version

def test_upgrade_functionality():
    """测试升级功能"""
    print("🔧 测试升级功能修复效果")
    print("=" * 50)
    
    # 1. 检查当前版本
    print(f"\n📋 当前版本: {current_version}")
    
    # 2. 创建UpdateManager实例
    updater = UpdateManager()
    print(f"📋 UpdateManager版本: {updater.current_version}")
    
    # 3. 测试检查更新
    print("\n🔍 测试检查更新功能...")
    try:
        latest_version, release_notes = updater.check_for_updates()
        if latest_version:
            print(f"✅ 检查更新成功")
            print(f"   最新版本: {latest_version}")
            print(f"   发布说明: {release_notes[:100]}..." if release_notes else "   无发布说明")
            
            # 4. 检查是否有新版本
            has_update = updater.is_new_version_available(latest_version)
            print(f"   有新版本: {'是' if has_update else '否'}")
            
            if has_update:
                print("\n⚠️  检测到新版本，但为了安全起见，不会自动执行升级")
                print("   如需升级，请手动运行升级功能")
            else:
                print("\n✅ 当前已是最新版本")
        else:
            print("❌ 检查更新失败")
            
    except Exception as e:
        print(f"❌ 检查更新异常: {e}")
    
    # 5. 测试网络连接
    print("\n🌐 测试网络连接...")
    try:
        import requests
        
        # 测试GitHub API
        response = requests.get('https://api.github.com/repos/yuanxiao9889/MJ-translate/releases/latest', timeout=10)
        if response.status_code == 200:
            print("✅ GitHub API连接正常")
        else:
            print(f"⚠️  GitHub API响应异常: {response.status_code}")
            
        # 测试下载链接
        download_url = 'https://github.com/yuanxiao9889/MJ-translate/archive/refs/tags/v1.0.4.zip'
        response = requests.head(download_url, timeout=10)
        if response.status_code == 200:
            print("✅ 下载链接可访问")
        else:
            print(f"⚠️  下载链接异常: {response.status_code}")
            
    except Exception as e:
        print(f"❌ 网络连接测试失败: {e}")
    
    # 6. 检查配置
    print("\n⚙️  检查配置...")
    config = updater.config
    if config.get('github_owner') and config.get('github_repo'):
        print(f"✅ GitHub配置正常: {config['github_owner']}/{config['github_repo']}")
    else:
        print("❌ GitHub配置缺失")
    
    print("\n" + "=" * 50)
    print("🎉 升级功能测试完成！")
    
    return True

def main():
    """主函数"""
    try:
        test_upgrade_functionality()
    except Exception as e:
        print(f"❌ 测试过程中发生异常: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)