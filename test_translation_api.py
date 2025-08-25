#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试翻译API功能是否正常工作
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.api import load_api_config, get_next_api_info, translate_text, get_current_platform
from services.credentials_manager import get_credentials_manager

def test_translation_functionality():
    """测试翻译功能"""
    print("=== 翻译API功能测试 ===")
    
    # 1. 加载API配置
    print("\n1. 加载API配置...")
    load_api_config()
    
    # 2. 检查当前平台
    current_platform = get_current_platform()
    print(f"当前翻译平台: {current_platform}")
    
    # 3. 获取当前平台的API信息
    print(f"\n2. 获取 {current_platform} 平台的API信息...")
    api_info, api_index = get_next_api_info(current_platform)
    
    if api_info:
        print(f"找到可用的API配置 (索引: {api_index})")
        # 隐藏敏感信息
        safe_info = {k: (v if k not in ['app_key', 'api_key'] else f"{v[:4]}***{v[-4:]}" if len(v) > 8 else "***") 
                    for k, v in api_info.items()}
        print(f"API配置: {safe_info}")
    else:
        print("❌ 未找到可用的API配置")
        return False
    
    # 4. 测试翻译功能
    print("\n3. 测试翻译功能...")
    test_text = "Hello, world!"
    print(f"测试文本: {test_text}")
    
    try:
        result = translate_text(test_text)
        print(f"翻译结果: {result}")
        
        if result and result != test_text:
            print("✅ 翻译功能正常工作")
            return True
        else:
            print("❌ 翻译功能异常：返回结果为空或未翻译")
            return False
            
    except Exception as e:
        print(f"❌ 翻译功能异常: {e}")
        return False

def test_credentials_manager():
    """测试凭证管理器"""
    print("\n=== 凭证管理器测试 ===")
    
    try:
        cred_manager = get_credentials_manager()
        credentials = cred_manager.get_credentials()
        
        print("\n凭证统计:")
        for cred_type, creds in credentials.items():
            active_count = len([c for c in creds if not c.get('disabled', False)])
            total_count = len(creds)
            print(f"  {cred_type}: {active_count}/{total_count} (活跃/总数)")
        
        return True
        
    except Exception as e:
        print(f"❌ 凭证管理器异常: {e}")
        return False

if __name__ == "__main__":
    print("开始测试翻译API功能...\n")
    
    # 测试凭证管理器
    cred_ok = test_credentials_manager()
    
    # 测试翻译功能
    trans_ok = test_translation_functionality()
    
    print("\n=== 测试结果 ===")
    print(f"凭证管理器: {'✅ 正常' if cred_ok else '❌ 异常'}")
    print(f"翻译功能: {'✅ 正常' if trans_ok else '❌ 异常'}")
    
    if cred_ok and trans_ok:
        print("\n🎉 所有测试通过！翻译API功能正常。")
    else:
        print("\n⚠️  存在问题，请检查上述错误信息。")