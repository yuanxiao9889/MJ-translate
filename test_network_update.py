#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试网络更新功能
验证修复后的更新机制是否能正常连接GitHub API
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.update_manager import UpdateManager
import time

def test_update_check():
    """测试更新检查功能"""
    print("=" * 50)
    print("测试更新检查功能")
    print("=" * 50)
    
    updater = UpdateManager()
    
    print("\n1. 测试检查更新功能...")
    try:
        latest_version, release_notes = updater.check_for_updates()
        
        if latest_version:
            print(f"✅ 成功获取最新版本: {latest_version}")
            print(f"📝 发布说明: {release_notes[:100]}..." if release_notes else "📝 无发布说明")
            
            # 检查是否有新版本
            if updater.is_new_version_available(latest_version):
                print(f"🆕 发现新版本可用: {latest_version} (当前版本: {updater.current_version})")
            else:
                print(f"✅ 当前版本已是最新: {updater.current_version}")
        else:
            print("❌ 无法获取版本信息")
            
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False
    
    return True

def test_download_simulation():
    """测试下载模拟（不实际下载）"""
    print("\n" + "=" * 50)
    print("测试下载功能模拟")
    print("=" * 50)
    
    updater = UpdateManager()
    
    def progress_callback(percent, status, message):
        print(f"[{percent:3d}%] {status}: {message}")
    
    print("\n2. 模拟下载过程...")
    print("注意: 这只是测试网络连接，不会实际下载和安装更新")
    
    try:
        # 这里我们只测试到获取release信息的步骤
        repo_owner = updater.config.get('github_owner')
        repo_name = updater.config.get('github_repo')
        
        if not repo_owner or not repo_name:
            print("❌ GitHub仓库配置不完整")
            return False
            
        api_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/releases/latest"
        print(f"🔗 API URL: {api_url}")
        
        # 使用相同的网络配置测试连接
        import requests
        session = requests.Session()
        session.trust_env = False
        session.proxies = {}
        headers = {
            'User-Agent': 'MJ-Translator-Update-Checker/1.0',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        print("🌐 测试网络连接...")
        response = session.get(api_url, headers=headers, timeout=30, proxies={})
        response.raise_for_status()
        
        latest_release = response.json()
        print(f"✅ 成功连接GitHub API")
        print(f"📦 最新版本: {latest_release.get('tag_name', 'unknown')}")
        
        # 检查可用的下载源
        assets = latest_release.get('assets', [])
        zipball_url = latest_release.get('zipball_url')
        
        print(f"📁 可用资源: {len(assets)} 个assets")
        if assets:
            for i, asset in enumerate(assets[:3]):  # 只显示前3个
                print(f"   {i+1}. {asset['name']} ({asset.get('size', 0)} bytes)")
        
        if zipball_url:
            print(f"📦 源代码ZIP: {zipball_url}")
            
        print("✅ 网络连接测试通过")
        return True
        
    except Exception as e:
        print(f"❌ 网络连接测试失败: {e}")
        return False

def main():
    """主测试函数"""
    print("🚀 开始测试修复后的更新功能")
    print(f"⏰ 测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 测试1: 检查更新
    test1_result = test_update_check()
    
    # 测试2: 下载模拟
    test2_result = test_download_simulation()
    
    # 总结
    print("\n" + "=" * 50)
    print("测试结果总结")
    print("=" * 50)
    print(f"✅ 更新检查功能: {'通过' if test1_result else '失败'}")
    print(f"✅ 网络连接测试: {'通过' if test2_result else '失败'}")
    
    if test1_result and test2_result:
        print("\n🎉 所有测试通过！更新功能已修复")
        print("💡 提示: 如果仍有问题，请检查防火墙或网络设置")
    else:
        print("\n❌ 部分测试失败，请检查网络连接")
        print("💡 建议: 确保能够访问 api.github.com")
    
    print("\n按任意键退出...")
    input()

if __name__ == "__main__":
    main()