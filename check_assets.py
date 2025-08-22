#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查GitHub Release的assets信息
"""

import requests
import json

def check_github_assets():
    """检查GitHub Release的assets"""
    try:
        api_url = "https://api.github.com/repos/yuanxiao9889/MJ-translate/releases/latest"
        print(f"正在检查: {api_url}")
        
        # 添加User-Agent头，避免GitHub API限制
        headers = {
            'User-Agent': 'MJ-translate-updater/1.0',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        response = requests.get(api_url, headers=headers, timeout=30)
        
        print(f"响应状态码: {response.status_code}")
        print(f"响应头: {dict(response.headers)}")
        
        if response.status_code == 200:
            data = response.json()
            
            print("\n=== 完整响应数据 ===")
            print(json.dumps(data, indent=2, ensure_ascii=False)[:2000])  # 只显示前2000字符
            
            print("\n=== GitHub Release 信息 ===")
            print(f"Tag Name: {data.get('tag_name', 'N/A')}")
            print(f"Release Name: {data.get('name', 'N/A')}")
            print(f"Published At: {data.get('published_at', 'N/A')}")
            print(f"Draft: {data.get('draft', False)}")
            print(f"Prerelease: {data.get('prerelease', False)}")
            
            assets = data.get('assets', [])
            print(f"\nAssets数量: {len(assets)}")
            print(f"Assets类型: {type(assets)}")
            
            if assets:
                print("\n=== Assets详情 ===")
                for i, asset in enumerate(assets):
                    print(f"{i+1}. {asset['name']}")
                    print(f"   大小: {asset.get('size', 0)} bytes ({asset.get('size', 0) / 1024 / 1024:.2f} MB)")
                    print(f"   下载URL: {asset.get('browser_download_url', 'N/A')}")
                    print(f"   Content Type: {asset.get('content_type', 'N/A')}")
                    print(f"   State: {asset.get('state', 'N/A')}")
                    print(f"   Created At: {asset.get('created_at', 'N/A')}")
                    print()
                
                # 检查ZIP文件
                zip_files = [asset for asset in assets if asset['name'].lower().endswith('.zip')]
                if zip_files:
                    print(f"✅ 找到 {len(zip_files)} 个ZIP文件")
                    for zip_file in zip_files:
                        print(f"   - {zip_file['name']} ({zip_file.get('size', 0) / 1024 / 1024:.2f} MB)")
                else:
                    print("⚠️ 没有找到ZIP文件")
                    print("所有文件扩展名:")
                    for asset in assets:
                        name = asset['name']
                        ext = name.split('.')[-1] if '.' in name else '无扩展名'
                        print(f"   - {name} -> .{ext}")
            else:
                print("❌ 没有找到任何assets")
                print("⚠️ 没有找到ZIP文件")
                
        else:
            print(f"❌ API请求失败: {response.status_code}")
            print(f"响应内容: {response.text[:1000]}")
            
    except Exception as e:
        print(f"❌ 检查失败: {str(e)}")
        import traceback
        traceback.print_exc()

# 同时检查特定的Release
def check_specific_release():
    """检查特定的Release (BUG修复)"""
    try:
        # 检查所有releases
        api_url = "https://api.github.com/repos/yuanxiao9889/MJ-translate/releases"
        print(f"\n正在检查所有releases: {api_url}")
        
        headers = {
            'User-Agent': 'MJ-translate-updater/1.0',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        response = requests.get(api_url, headers=headers, timeout=30)
        
        if response.status_code == 200:
            releases = response.json()
            print(f"\n找到 {len(releases)} 个releases")
            
            for i, release in enumerate(releases[:3]):  # 只显示前3个
                print(f"\n=== Release {i+1} ===")
                print(f"Tag: {release.get('tag_name', 'N/A')}")
                print(f"Name: {release.get('name', 'N/A')}")
                print(f"Draft: {release.get('draft', False)}")
                print(f"Prerelease: {release.get('prerelease', False)}")
                print(f"Assets数量: {len(release.get('assets', []))}")
                
                assets = release.get('assets', [])
                if assets:
                    print("Assets:")
                    for asset in assets:
                        print(f"  - {asset['name']} ({asset.get('size', 0) / 1024 / 1024:.2f} MB)")
                        
        else:
            print(f"❌ 获取所有releases失败: {response.status_code}")
            
    except Exception as e:
        print(f"❌ 检查特定release失败: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("=== 检查最新Release ===")
    check_github_assets()
    
    print("\n" + "="*50)
    print("=== 检查所有Releases ===")
    check_specific_release()