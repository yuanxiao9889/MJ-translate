<<<<<<< HEAD
# MJ 提示词翻译工具

<div align="center">

![MJ Translator](mj_icon.ico)

**一个功能强大的 Midjourney 提示词翻译与管理工具**

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://python.org)
[![CustomTkinter](https://img.shields.io/badge/GUI-CustomTkinter-green.svg)](https://github.com/TomSchimansky/CustomTkinter)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

</div>

## 📖 项目简介

MJ 提示词翻译工具是一个专为 Midjourney 用户设计的桌面应用程序，提供智能翻译、标签管理、历史记录、收藏夹等功能。支持多种翻译平台（百度翻译、智谱AI等），帮助用户高效创建和管理 AI 绘画提示词。

## ✨ 核心功能

### 🌐 智能翻译
- **多平台支持**：集成百度翻译、智谱AI、智谱GLM-4.5等翻译服务
- **实时翻译**：支持中英文互译，自动检测语言类型
- **批量处理**：支持多行文本同时翻译
- **翻译历史**：自动保存翻译记录，支持搜索和筛选

### 🏷️ 标签管理系统
- **分类标签**：支持头部标签和尾部标签分类管理
- **标签模板**：预设常用标签组合，一键应用
- **智能拼接**：自动将标签与翻译结果组合
- **标签导入导出**：支持CSV格式的标签数据管理
- **可视化编辑**：直观的标签编辑界面，支持拖拽排序

### 📄 分页管理
- **多页面支持**：创建多个翻译页面，独立管理不同项目
- **页面导航**：便捷的页面切换和管理功能
- **页面标签**：每个页面可独立配置标签组合
- **批量操作**：支持页面的批量创建、删除和清空

### 💾 数据管理
- **收藏夹功能**：保存常用的翻译结果和提示词
- **历史记录**：完整的操作历史，支持日期筛选
- **云端同步**：支持阿里云OSS存储，多设备数据同步
- **数据备份**：自动备份重要数据，防止数据丢失

### 🎨 用户界面
- **现代化设计**：基于CustomTkinter的现代化界面
- **响应式布局**：自适应窗口大小变化
- **虚拟滚动**：高性能的大数据量显示
- **主题支持**：支持系统主题自动切换
- **快捷键支持**：丰富的键盘快捷键操作

### 🔧 扩展功能
- **浏览器扩展**：配套的Chrome扩展，支持网页内容快速翻译
- **系统托盘**：最小化到系统托盘，后台运行
- **HTTP桥接**：本地HTTP服务，支持外部程序调用
- **图片处理**：集成图片裁剪和处理功能
- **预设扩写**：支持提示词的智能扩写和优化

## 🚀 快速开始

### 环境要求

- **操作系统**：Windows 10/11
- **Python版本**：3.8 或更高版本
- **内存要求**：建议 4GB 以上
- **磁盘空间**：至少 500MB 可用空间

### 安装步骤

#### 方法一：使用启动脚本（推荐）

1. **下载项目**
   ```bash
   git clone https://github.com/yuanxiao9889/MJ-.git
   cd MJ-
   ```

2. **运行启动脚本**
   ```bash
   # Windows
   start.bat
   ```
   
   启动脚本会自动：
   - 检查Python环境
   - 安装所需依赖
   - 启动应用程序

#### 方法二：手动安装

1. **克隆仓库**
   ```bash
   git clone https://github.com/yuanxiao9889/MJ-.git
   cd MJ-
   ```

2. **安装依赖**
   ```bash
   pip install customtkinter Pillow requests pyperclip tkcalendar pystray oss2 cryptography
   ```

3. **启动应用**
   ```bash
   python main.py
   ```

### 初次配置

1. **配置翻译API**
   - 启动应用后，点击顶部的「⚙️ 设置」按钮
   - 选择「API与存储管理」
   - 添加您的翻译服务API密钥

2. **选择翻译平台**
   - 在顶部下拉菜单中选择要使用的翻译平台
   - 支持：百度翻译、智谱AI、智谱GLM-4.5

3. **配置云端存储（可选）**
   - 在设置中配置阿里云OSS信息
   - 启用数据云端同步功能

## 📚 使用指南

### 基础翻译

1. **文本翻译**
   - 在左侧输入框中输入要翻译的文本
   - 点击「翻译」按钮或使用快捷键 `Ctrl+Enter`
   - 翻译结果将显示在右侧输出框中

2. **标签应用**
   - 在标签区域选择需要的标签
   - 标签会自动添加到翻译结果中
   - 支持头部标签和尾部标签的组合使用

### 标签管理

1. **创建标签**
   - 点击标签区域的「➕」按钮
   - 输入标签名称和内容
   - 选择标签类型（头部/尾部）

2. **编辑标签**
   - 右键点击标签，选择「编辑」
   - 修改标签内容后保存

3. **标签导入导出**
   - 使用「标签管理」功能导出为CSV文件
   - 支持从CSV文件批量导入标签

### 分页功能

1. **创建页面**
   - 点击页面导航区的「➕ 新建」按钮
   - 输入页面名称
   - 新页面将自动切换为当前页面

2. **页面切换**
   - 点击页面标签切换到对应页面
   - 每个页面独立保存标签状态

3. **页面管理**
   - 右键点击页面标签进行重命名或删除
   - 使用「🗑️ 清空」按钮清空所有页面

### 历史记录与收藏

1. **查看历史**
   - 点击「📖 历史记录」按钮
   - 支持按日期筛选和关键词搜索
   - 可以重新应用历史翻译结果

2. **收藏管理**
   - 点击翻译结果旁的「⭐ 收藏」按钮
   - 在「⭐ 收藏夹」中管理收藏的内容
   - 支持分类和标签管理

### 浏览器扩展

1. **安装扩展**
   - 打开Chrome浏览器
   - 进入扩展管理页面
   - 加载 `floating_tag_ball` 文件夹作为未打包扩展

2. **使用扩展**
   - 在网页中选择文本
   - 点击浮动的翻译球
   - 翻译结果会自动发送到桌面应用

## 🏗️ 项目架构

### 目录结构

```
mj_translato/
├── main.py                 # 应用入口
├── app.py                  # 应用启动器
├── services/               # 核心服务层
│   ├── api.py             # API接口管理
│   ├── tags.py            # 标签管理服务
│   ├── bridge.py          # HTTP桥接服务
│   ├── credentials_manager.py  # 凭据管理
│   ├── data_processor.py  # 数据处理
│   ├── logger.py          # 日志服务
│   └── ...
├── views/                  # 视图层
│   ├── ui_main.py         # 主界面
│   ├── page_manager.py    # 页面管理
│   ├── history.py         # 历史记录界面
│   ├── favorites.py       # 收藏夹界面
│   └── ...
├── floating_tag_ball/      # 浏览器扩展
├── images/                 # 图片资源
├── logs/                   # 日志文件
└── config files           # 配置文件
```

### 架构设计

项目采用**分层架构**设计，遵循**关注点分离**原则：

- **应用层** (`app.py`, `main.py`)：负责应用启动和生命周期管理
- **视图层** (`views/`)：负责用户界面和交互逻辑
- **服务层** (`services/`)：负责业务逻辑和数据处理
- **工具层** (`utils.py`, `image_tools.py`)：提供通用工具函数

### 核心组件

1. **翻译引擎**：支持多种翻译API的统一接口
2. **标签系统**：灵活的标签管理和应用机制
3. **数据持久化**：JSON文件存储 + 云端同步
4. **HTTP桥接**：与浏览器扩展的通信桥梁
5. **虚拟滚动**：高性能的大数据量UI渲染

## ⚙️ 配置说明

### 主要配置文件

- **`config.json`**：主配置文件，包含API配置和平台选择
- **`credentials.json`**：加密存储的API密钥和凭据
- **`tags.json`**：标签数据存储
- **`pages_data.json`**：页面数据存储
- **`oss_config.json`**：阿里云OSS配置
- **`sync_config.json`**：同步配置

### API配置

支持的翻译平台及其配置：

```json
{
  "baidu": {
    "app_id": "your_app_id",
    "app_key": "your_app_key"
  },
  "zhipu": {
    "api_key": "your_api_key"
  }
}
```

### 云端存储配置

```json
{
  "ACCESS_KEY_ID": "your_access_key",
  "ACCESS_KEY_SECRET": "your_secret_key",
  "BUCKET_NAME": "your_bucket",
  "ENDPOINT": "your_endpoint"
}
```

## 🔧 开发指南

### 开发环境搭建

1. **克隆项目**
   ```bash
   git clone https://github.com/yuanxiao9889/MJ-.git
   cd MJ-
   ```

2. **创建虚拟环境**
   ```bash
   python -m venv venv
   venv\Scripts\activate  # Windows
   ```

3. **安装开发依赖**
   ```bash
   pip install -r requirements-dev.txt
   ```

### 代码规范

- **代码风格**：遵循 PEP 8 规范
- **类型注解**：使用 Python 类型提示
- **文档字符串**：使用 Google 风格的文档字符串
- **错误处理**：统一的异常处理机制

### 测试

```bash
# 运行单元测试
pytest tests/

# 代码覆盖率
pytest --cov=services tests/

# 类型检查
mypy services/
```

### 构建与部署

```bash
# 打包应用
pyinstaller --onefile --windowed main.py

# 创建安装包
# 使用 NSIS 或其他打包工具
```

## 🤝 贡献指南

我们欢迎所有形式的贡献！

### 如何贡献

1. **Fork 项目**
2. **创建特性分支** (`git checkout -b feature/AmazingFeature`)
3. **提交更改** (`git commit -m 'Add some AmazingFeature'`)
4. **推送到分支** (`git push origin feature/AmazingFeature`)
5. **创建 Pull Request**

### 贡献类型

- 🐛 **Bug 修复**：修复已知问题
- ✨ **新功能**：添加新的功能特性
- 📚 **文档改进**：完善文档和注释
- 🎨 **UI/UX 改进**：优化用户界面和体验
- ⚡ **性能优化**：提升应用性能
- 🧪 **测试**：添加或改进测试用例

### 开发规范

- 提交前请运行测试确保代码质量
- 遵循现有的代码风格和架构模式
- 为新功能添加相应的文档和测试
- 保持向后兼容性

## 📋 更新日志

### v2.0.0 (2024-01-XX)
- ✨ 实现虚拟滚动，支持大数据量显示
- 🎨 优化UI界面，提升用户体验
- 🏗️ 重构项目架构，采用模块化设计
- 📄 添加分页管理功能
- 🔐 增强安全性，加密存储敏感信息
- ☁️ 支持云端数据同步

### v1.5.0 (2023-12-XX)
- 🌐 添加智谱AI翻译支持
- 🏷️ 完善标签管理系统
- 📖 优化历史记录功能
- 🔧 改进配置管理

### v1.0.0 (2023-10-XX)
- 🎉 首个正式版本发布
- 🌐 支持百度翻译API
- 🏷️ 基础标签管理功能
- 💾 本地数据存储
- 🎨 现代化UI界面

## ❓ 常见问题

### 安装问题

**Q: 提示缺少依赖库怎么办？**
A: 运行 `pip install -r requirements.txt` 安装所有依赖，或使用 `start.bat` 自动安装。

**Q: Python版本不兼容？**
A: 请确保使用 Python 3.8 或更高版本。

### 使用问题

**Q: 翻译失败怎么办？**
A: 检查网络连接和API密钥配置，确保API服务正常。

**Q: 数据丢失了怎么办？**
A: 检查 `backup/` 目录中的备份文件，或从云端同步恢复。

**Q: 界面显示异常？**
A: 尝试重启应用，或检查系统DPI设置。

### 性能问题

**Q: 应用运行缓慢？**
A: 清理历史数据，关闭不必要的功能，或升级硬件配置。

**Q: 内存占用过高？**
A: 重启应用释放内存，或减少同时打开的页面数量。

## 📞 支持与反馈

- **GitHub Issues**：[提交问题和建议](https://github.com/yuanxiao9889/MJ-/issues)
- **讨论区**：[参与社区讨论](https://github.com/yuanxiao9889/MJ-/discussions)
- **邮箱**：yuanxiao9889@example.com

## 📄 许可证

本项目采用 [MIT 许可证](LICENSE)。

```
MIT License

Copyright (c) 2024 MJ Translator Contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMplied, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## 🙏 致谢

感谢以下开源项目和贡献者：

- [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) - 现代化的Tkinter界面库
- [Pillow](https://python-pillow.org/) - Python图像处理库
- [Requests](https://requests.readthedocs.io/) - HTTP请求库
- [PyStray](https://github.com/moses-palmer/pystray) - 系统托盘支持
- [TkCalendar](https://github.com/j4321/tkcalendar) - 日历组件

特别感谢所有为项目贡献代码、报告问题和提供建议的开发者们！

---

<div align="center">

**如果这个项目对您有帮助，请给我们一个 ⭐ Star！**

[🏠 首页](https://github.com/yuanxiao9889/MJ-) • [📖 文档](https://github.com/yuanxiao9889/MJ-/wiki) • [🐛 问题反馈](https://github.com/yuanxiao9889/MJ-/issues) • [💬 讨论](https://github.com/yuanxiao9889/MJ-/discussions)

</div>
