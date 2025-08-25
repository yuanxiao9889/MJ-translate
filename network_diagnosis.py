#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
网络诊断脚本 - 诊断升级功能网络问题
"""

import requests
import socket
import time
import json
from services.update_manager import UpdateManager

def test_dns_resolution():
    """测试DNS解析"""
    print("\n=== DNS解析测试 ===")
    domains = [
        'api.github.com',
        'codeload.github.com',
        'github.com'
    ]
    
    for domain in domains:
        try:
            ip = socket.gethostbyname(domain)
            print(f"✅ {domain} -> {ip}")
        except Exception as e:
            print(f"❌ {domain} -> 解析失败: {e}")

def test_network_connectivity():
    """测试网络连通性"""
    print("\n=== 网络连通性测试 ===")
    
    # 测试GitHub API
    try:
        response = requests.get('https://api.github.com/repos/yuanxiao9889/MJ-translate/releases/latest', timeout=10)
        print(f"✅ GitHub API: {response.status_code} - {response.json()['tag_name']}")
    except Exception as e:
        print(f"❌ GitHub API: {e}")
    
    # 测试codeload下载
    try:
        url = 'https://codeload.github.com/yuanxiao9889/MJ-translate/zip/refs/tags/v1.0.4'
        response = requests.get(url, timeout=30, stream=True)
        content_length = response.headers.get('content-length', 'Unknown')
        print(f"✅ Codeload下载: {response.status_code} - 大小: {content_length}")
        response.close()
    except Exception as e:
        print(f"❌ Codeload下载: {e}")

def test_proxy_settings():
    """测试代理设置"""
    print("\n=== 代理设置检查 ===")
    
    import os
    proxy_vars = ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']
    
    for var in proxy_vars:
        value = os.environ.get(var)
        if value:
            print(f"⚠️  发现代理设置: {var} = {value}")
        else:
            print(f"✅ {var}: 未设置")

def test_update_manager():
    """测试UpdateManager功能"""
    print("\n=== UpdateManager测试 ===")
    
    try:
        updater = UpdateManager()
        print(f"✅ 当前版本: {updater.current_version}")
        
        # 测试检查更新
        latest_version, release_notes = updater.check_for_updates()
        if latest_version:
            print(f"✅ 检查更新成功: {latest_version}")
            print(f"   发布说明: {release_notes[:50]}..." if release_notes else "   无发布说明")
        else:
            print("❌ 检查更新失败")
            
    except Exception as e:
        print(f"❌ UpdateManager错误: {e}")

def test_session_configuration():
    """测试会话配置"""
    print("\n=== 会话配置测试 ===")
    
    # 测试不同的会话配置
    configs = [
        {"name": "默认配置", "trust_env": True, "proxies": None},
        {"name": "禁用环境变量", "trust_env": False, "proxies": {}},
        {"name": "UpdateManager配置", "trust_env": False, "proxies": {}}
    ]
    
    for config in configs:
        try:
            session = requests.Session()
            session.trust_env = config["trust_env"]
            if config["proxies"] is not None:
                session.proxies = config["proxies"]
            
            response = session.get('https://codeload.github.com/yuanxiao9889/MJ-translate/zip/refs/tags/v1.0.4', 
                                 timeout=10, stream=True)
            print(f"✅ {config['name']}: {response.status_code}")
            response.close()
        except Exception as e:
            print(f"❌ {config['name']}: {e}")

def main():
    """主函数"""
    print("🔍 MJ-Translate 网络诊断工具")
    print("=" * 50)
    
    test_dns_resolution()
    test_proxy_settings()
    test_network_connectivity()
    test_session_configuration()
    test_update_manager()
    
    print("\n=== 诊断完成 ===")
    print("\n💡 解决建议:")
    print("1. 如果DNS解析失败，尝试更换DNS服务器（8.8.8.8, 114.114.114.114）")
    print("2. 如果发现代理设置，检查代理是否正常工作")
    print("3. 如果网络连通性测试失败，检查防火墙和网络设置")
    print("4. 如果间歇性失败，可能是网络不稳定，建议重试")
    print("5. 企业网络环境可能需要联系网络管理员")

if __name__ == "__main__":
    main()