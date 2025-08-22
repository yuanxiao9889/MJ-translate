# MJ Translator 虚拟环境使用指南

## 概述

本项目现已配置Python虚拟环境，确保在不同电脑上都能稳定运行，避免依赖冲突问题。

## 快速开始

### 方法一：使用自动化脚本（推荐）

1. **初始化环境**：
   ```bash
   setup.bat
   ```
   这个脚本会自动：
   - 检查Python安装
   - 创建虚拟环境
   - 安装所有依赖
   - 测试安装结果

2. **启动程序**：
   ```bash
   start.bat
   ```

### 方法二：手动操作

1. **创建虚拟环境**：
   ```bash
   python -m venv venv
   ```

2. **激活虚拟环境**：
   ```bash
   # Windows
   venv\Scripts\activate
   
   # Linux/Mac
   source venv/bin/activate
   ```

3. **安装依赖**：
   ```bash
   pip install -r requirements.txt
   ```

4. **运行程序**：
   ```bash
   python main.py
   ```

## 依赖包说明

项目包含以下主要依赖：

- **customtkinter**: 现代化GUI界面
- **Pillow**: 图像处理
- **requests**: HTTP请求
- **pyperclip**: 剪贴板操作
- **tkcalendar**: 日历组件
- **pystray**: 系统托盘
- **oss2**: 阿里云OSS存储
- **semver**: 版本管理
- **chardet**: 字符编码检测

## 部署到新电脑

1. **复制项目文件**到目标电脑
2. **确保Python已安装**（Python 3.7+）
3. **运行setup.bat**进行环境初始化
4. **运行start.bat**启动程序

## 故障排除

### 常见问题

1. **Python未找到**：
   - 确保Python已正确安装
   - 检查PATH环境变量
   - 重新安装Python并勾选"Add to PATH"

2. **虚拟环境激活失败**：
   - 检查venv文件夹是否存在
   - 重新运行setup.bat
   - 手动删除venv文件夹后重新创建

3. **依赖安装失败**：
   - 检查网络连接
   - 尝试使用国内镜像：
     ```bash
     pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple/
     ```

4. **程序启动失败**：
   - 检查所有依赖是否正确安装
   - 查看错误日志
   - 确认虚拟环境已激活

### 重置环境

如果遇到严重问题，可以完全重置环境：

```bash
# 删除虚拟环境
rmdir /s venv

# 重新初始化
setup.bat
```

## 开发者说明

### 更新依赖

当添加新的依赖包时：

1. 在虚拟环境中安装新包
2. 更新requirements.txt：
   ```bash
   pip freeze > requirements.txt
   ```

### 版本管理

- 虚拟环境文件夹(`venv/`)已添加到`.gitignore`
- 只提交`requirements.txt`文件
- 每个开发者需要本地创建自己的虚拟环境

## 优势

✅ **环境隔离**：避免与系统Python包冲突  
✅ **版本锁定**：确保所有环境使用相同版本的依赖  
✅ **便携性**：可在任何支持Python的系统上运行  
✅ **自动化**：一键安装和启动  
✅ **稳定性**：减少因环境差异导致的问题  

---

**注意**：首次运行请使用`setup.bat`进行环境初始化，后续可直接使用`start.bat`启动程序。