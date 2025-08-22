# 模块化更新功能说明

## 概述

为了避免 `ui_main.py` 文件过于庞大，我们将更新功能独立成了一个单独的模块。这样做的好处包括：

- **代码组织更清晰**：更新相关的所有逻辑都集中在一个专门的模块中
- **维护更容易**：修改更新功能时不需要在庞大的 ui_main.py 中查找
- **复用性更好**：其他地方也可以轻松调用更新对话框
- **测试更方便**：可以独立测试更新功能

## 文件结构

```
views/
├── ui_main.py          # 主UI文件（已简化）
└── update_dialog.py    # 独立的更新对话框模块
```

## 核心组件

### UpdateDialog 类

位于 `views/update_dialog.py`，包含以下功能：

- **检查更新**：连接 GitHub API 获取最新版本信息
- **下载更新**：使用进度对话框下载并应用更新
- **测试网络**：验证网络连接和 GitHub API 访问
- **日志显示**：实时显示操作过程和结果

### 主要方法

- `show()`：显示更新对话框
- `_check_for_updates()`：检查是否有新版本
- `_download_update()`：下载并应用更新
- `_test_network()`：测试网络连接

## 使用方法

### 在主程序中调用

```python
from views.update_dialog import open_update_dialog

# 在按钮点击事件中调用
ctk.CTkButton(parent, text="🔄 检查更新", 
             command=lambda: open_update_dialog(root))
```

### 独立测试

运行测试脚本：
```bash
python test_modular_update.py
```

## 网络配置优化

更新功能包含以下网络优化：

- **禁用代理**：避免代理连接问题
- **设置超时**：防止长时间等待
- **重试机制**：提高连接成功率
- **错误分类处理**：针对不同错误类型给出相应提示

## 版本兼容性

支持以下版本格式：
- 标准语义化版本：`1.0.0`, `2.1.3`
- 非标准版本号：`BUG修复`, `功能更新` 等

## 技术特点

1. **异步处理**：网络请求在后台线程执行，不阻塞UI
2. **进度反馈**：实时显示下载进度和操作状态
3. **错误处理**：完善的异常捕获和用户友好的错误提示
4. **界面友好**：现代化的 CustomTkinter 界面设计

## 维护说明

- 更新功能的修改只需要编辑 `views/update_dialog.py`
- 网络配置在 `services/update_manager.py` 中
- 进度对话框在 `components/update_progress_dialog.py` 中

这种模块化设计使得代码更加清晰、易于维护和扩展。