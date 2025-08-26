#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from services.update_manager import UpdateManager
import json

def test_download_url():
    """测试_get_download_url_with_fallback方法"""
    try:
        # 初始化UpdateManager
        um = UpdateManager()
        print(f"UpdateManager初始化成功，当前版本: {um.current_version}")
        
        # 检查更新
        print("正在检查更新...")
        latest_version, release_notes = um.check_for_updates()
        print(f"最新版本: {latest_version}")
        
        if latest_version:
            # 读取缓存的release数据
            print("测试_get_download_url_with_fallback方法...")
            cache_file = '.update_cache/latest_release.json'
            with open(cache_file, 'r', encoding='utf-8') as f:
                release_data = json.load(f)
            
            # 测试获取下载URL
            url, name, size = um._get_download_url_with_fallback(release_data)
            print(f"下载URL: {url}")
            print(f"文件名: {name}")
            print(f"文件大小: {size} bytes")
            print("✅ _get_download_url_with_fallback方法测试成功!")
            
            # 测试版本比较
            is_new = um.is_new_version_available(latest_version)
            print(f"是否有新版本: {is_new}")
            
        else:
            print("❌ 无法获取最新版本信息")
            
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_download_url()