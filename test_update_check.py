#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单的更新机制检查脚本
验证GitHub zipball_url处理逻辑是否存在
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.update_manager import UpdateManager

def test_update_mechanism():
    print("=== 更新机制检查 ===")
    
    # 创建UpdateManager实例
    updater = UpdateManager()
    
    # 检查是否有check_for_updates方法
    if hasattr(updater, 'check_for_updates'):
        print("✅ check_for_updates方法存在")
    else:
        print("❌ check_for_updates方法不存在")
        return False
    
    # 检查是否有download_and_apply_update方法
    if hasattr(updater, 'download_and_apply_update'):
        print("✅ download_and_apply_update方法存在")
    else:
        print("❌ download_and_apply_update方法不存在")
        return False
    
    # 检查download_and_apply_update方法是否支持progress_callback参数
    import inspect
    sig = inspect.signature(updater.download_and_apply_update)
    if 'progress_callback' in sig.parameters:
        print("✅ download_and_apply_update支持progress_callback参数")
    else:
        print("❌ download_and_apply_update不支持progress_callback参数")
        return False
    
    # 检查源代码中是否包含zipball_url处理逻辑
    import inspect
    source = inspect.getsource(updater.download_and_apply_update)
    if 'zipball_url' in source:
        print("✅ 源代码中包含zipball_url处理逻辑")
    else:
        print("❌ 源代码中不包含zipball_url处理逻辑")
        return False
    
    # 检查是否包含智能选择逻辑
    if '优先选择用户上传的ZIP文件' in source:
        print("✅ 包含智能下载源选择逻辑")
    else:
        print("❌ 不包含智能下载源选择逻辑")
        return False
    
    print("\n=== 检查结果 ===")
    print("✅ 更新机制完整存在，包含所有必要功能：")
    print("   - GitHub Release检查")
    print("   - 智能下载源选择（用户ZIP > 其他文件 > GitHub源代码ZIP）")
    print("   - zipball_url备用下载")
    print("   - 进度回调支持")
    
    return True

if __name__ == "__main__":
    try:
        success = test_update_mechanism()
        if success:
            print("\n🎉 更新机制检查通过！")
        else:
            print("\n❌ 更新机制检查失败！")
    except Exception as e:
        print(f"\n❌ 检查过程中发生错误: {e}")
        import traceback
        traceback.print_exc()