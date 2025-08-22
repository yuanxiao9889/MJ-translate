# GitHub Release 创建指南

## 问题诊断

经过测试发现，您的GitHub仓库 `yuanxiao9889/MJ-translate` 存在且可以正常访问，但是**没有创建任何Release版本**。

更新功能需要通过GitHub的Release API来获取版本信息，仅仅推送代码到仓库是不够的，必须创建Release版本。

## 解决方案：创建GitHub Release

### 方法一：通过GitHub网页界面创建Release

1. **访问您的仓库**
   - 打开浏览器，访问：https://github.com/yuanxiao9889/MJ-translate

2. **进入Releases页面**
   - 在仓库主页右侧找到 "Releases" 链接
   - 或直接访问：https://github.com/yuanxiao9889/MJ-translate/releases

3. **创建新Release**
   - 点击 "Create a new release" 按钮
   - 如果是第一次创建，会显示 "Create a new release" 的大按钮

4. **填写Release信息**
   ```
   Tag version: v1.0.1  (建议格式：v + 版本号)
   Release title: MJ翻译工具 v1.0.1
   Description: 
   - 修复更新功能404错误
   - 增加版本对比显示
   - 优化错误处理和用户提示
   - 其他改进和修复
   ```

5. **发布Release**
   - 确认信息无误后，点击 "Publish release" 按钮

### 方法二：通过GitHub CLI创建Release（可选）

如果您安装了GitHub CLI，可以使用命令行：

```bash
# 安装GitHub CLI（如果未安装）
# 访问：https://cli.github.com/

# 登录GitHub
gh auth login

# 创建Release
gh release create v1.0.1 --title "MJ翻译工具 v1.0.1" --notes "修复更新功能，增加版本对比显示"
```

## 版本号建议

根据您当前的版本是 `1.0.0`，建议新版本使用：
- `v1.0.1` - 修复版本（推荐）
- `v1.1.0` - 功能更新版本
- `v2.0.0` - 重大更新版本

## 验证Release创建成功

创建Release后，您可以：

1. **检查Release页面**
   - 访问：https://github.com/yuanxiao9889/MJ-translate/releases
   - 应该能看到新创建的Release

2. **测试更新功能**
   - 运行您的MJ翻译工具
   - 点击检查更新
   - 应该能正常显示版本对比信息

3. **运行API测试**
   ```bash
   python test_github_api.py
   ```
   - 应该显示找到Release版本

## 注意事项

1. **Tag版本格式**：建议使用 `v1.0.1` 格式，程序会自动去掉 `v` 前缀进行版本比较

2. **版本号规则**：遵循语义化版本控制（Semantic Versioning）
   - 主版本号：不兼容的API修改
   - 次版本号：向下兼容的功能性新增
   - 修订号：向下兼容的问题修正

3. **Release说明**：详细描述更新内容，方便用户了解改进

4. **自动更新**：创建Release后，更新功能将能够：
   - 检测到新版本
   - 显示版本对比
   - 提供下载和更新选项

## 后续维护

每次发布新版本时，记得：
1. 更新 `services/__init__.py` 中的 `__version__`
2. 推送代码到GitHub
3. 创建对应的Release版本

这样更新功能就能正常工作了！