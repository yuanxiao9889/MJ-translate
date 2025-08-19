# 标签悬浮球助手 - Edge浏览器版本

## 🚀 重大更新：直接网页截图（无需选择屏幕）

### ✅ 核心功能
- **直接网页截图**：无需选择屏幕，直接截取当前网页内容
- **Edge浏览器优化**：专为Microsoft Edge浏览器设计
- **智能降级**：多种截图方案自动切换
- **零配置**：安装即用，无需额外设置

### 📦 安装方法

#### 方法1：开发者模式（推荐）
1. 下载 `floating_tag_ball_edge.zip`
2. 打开Edge浏览器，访问 `edge://extensions/`
3. 开启右上角的"开发者模式"
4. 点击"加载解压缩的扩展"，选择解压后的文件夹

#### 方法2：拖放安装
1. 直接将 `floating_tag_ball_edge.zip` 拖到 `edge://extensions/` 页面
2. 确认安装

### 🎯 使用方法

#### 基本使用
1. **打开任意网页**
2. **点击蓝色悬浮球**（页面右下角）
3. **直接选择网页区域**（无需选择屏幕！）
4. **添加标签**并保存

#### 高级测试
按F12打开控制台，使用以下命令：
```javascript
// 测试直接网页截图
window.testDirectCapture.visible()   // 截图可见区域
window.testDirectCapture.fullPage()   // 截图整个页面
window.testDirectCapture.custom()     // 自定义区域

// 验证功能
window.edgeVerification.checkStatus()
```

### 🔧 技术特性

#### 截图方案（自动选择）
1. **优先方案**：直接网页截图API
2. **备选方案**：DOM渲染截图
3. **降级方案**：Canvas占位图

#### 浏览器兼容性
- ✅ Microsoft Edge 79+
- ✅ Windows 10/11
- ✅ 无需额外权限

### 🆕 版本亮点

#### v0.2.2 - Edge专用版本
- 🎉 **无需选择屏幕**：直接截取当前网页
- 🎯 **Edge优化**：移除Chrome特有依赖
- ⚡ **零配置**：安装即用
- 🔧 **智能降级**：多种方案自动切换

### 📋 文件结构
```
floating_tag_ball/
├── manifest.json          # Edge兼容配置
├── content.js            # 主功能脚本
├── direct_page_capture.js # 直接网页截图模块
├── test_direct_capture.js # 测试脚本
├── verify_edge_compatibility.js # 兼容性验证
├── edge_install_guide.md  # 详细安装指南
└── README_EDGE.md        # 本文件
```

### 🚨 注意事项

1. **首次使用**：可能需要刷新页面激活扩展
2. **权限提示**：Edge可能会询问屏幕捕获权限，选择"允许"
3. **测试环境**：建议在普通网页测试，避免在扩展页面测试

### 🔍 故障排除

#### 截图不工作？
1. 检查扩展是否已启用
2. 刷新页面重试
3. 查看控制台错误信息
4. 使用 `window.edgeVerification.checkStatus()` 检查状态

#### 悬浮球不显示？
1. 确保在普通网页（非扩展页面）
2. 检查扩展权限设置
3. 重启浏览器

### 📞 支持

遇到问题？请提供以下信息：
1. Edge浏览器版本
2. 操作系统版本
3. 控制台错误信息
4. 复现步骤

---

**🎉 现在享受无需选择屏幕的直接网页截图体验吧！**