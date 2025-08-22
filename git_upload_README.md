# GitHub一键上传脚本使用说明

## 概述

这是一个功能完善的GitHub一键上传脚本，专为Windows环境设计，支持自动检测Git仓库状态、添加变更文件、生成提交信息并推送到远程仓库。

## 文件说明

- `git_upload.ps1` - 主要的PowerShell脚本文件
- `git_upload.bat` - 批处理启动文件，双击即可运行
- `git_upload_config_template.json` - 配置文件模板
- `git_upload_README.md` - 本说明文档

## 快速开始

### 方法一：双击运行（推荐）
1. 双击 `git_upload.bat` 文件
2. 按照提示操作即可

### 方法二：PowerShell命令行
```powershell
# 基本用法
.\git_upload.ps1

# 自定义提交信息
.\git_upload.ps1 -Message "修复重要bug"

# 推送到指定分支
.\git_upload.ps1 -Branch "develop"

# 推送到指定远程仓库
.\git_upload.ps1 -Remote "upstream"
```

## 功能特性

### 🔍 自动检测
- ✅ 检测当前目录是否为Git仓库
- ✅ 检测Git环境是否正确安装
- ✅ 检测网络连接状态
- ✅ 检测远程仓库配置

### 📁 文件管理
- ✅ 自动添加所有变更文件（新增、修改、删除）
- ✅ 显示详细的文件变更状态
- ✅ 支持忽略特定文件类型

### 💬 提交信息
- ✅ 自动生成带时间戳的提交信息
- ✅ 支持自定义提交信息
- ✅ 包含用户和计算机信息

### 🚀 推送功能
- ✅ 自动推送到默认分支
- ✅ 支持指定远程仓库和分支
- ✅ 支持强制推送（谨慎使用）

### 🛡️ 错误处理
- ✅ 网络连接检测
- ✅ 权限验证
- ✅ 冲突处理提示
- ✅ 回滚机制
- ✅ 详细的错误信息

### 🎨 用户界面
- ✅ 彩色输出，清晰易读
- ✅ 中文界面支持
- ✅ 详细的操作指引
- ✅ 确认提示机制

## 参数说明

| 参数 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `-Message` | 字符串 | 自定义提交信息 | `-Message "修复登录bug"` |
| `-Remote` | 字符串 | 远程仓库名称 | `-Remote "upstream"` |
| `-Branch` | 字符串 | 目标分支名称 | `-Branch "develop"` |
| `-Help` | 开关 | 显示帮助信息 | `-Help` |
| `-Config` | 开关 | 配置远程仓库 | `-Config` |
| `-Force` | 开关 | 强制推送模式 | `-Force` |

## 使用示例

### 基本使用
```powershell
# 最简单的使用方式
.\git_upload.ps1
```

### 自定义提交信息
```powershell
# 添加自定义提交信息
.\git_upload.ps1 -Message "添加新功能：用户登录模块"
```

### 推送到不同分支
```powershell
# 推送到开发分支
.\git_upload.ps1 -Branch "develop" -Message "开发版本更新"
```

### 推送到不同的远程仓库
```powershell
# 推送到上游仓库
.\git_upload.ps1 -Remote "upstream" -Branch "main"
```

### 强制推送（谨慎使用）
```powershell
# 强制推送，跳过确认
.\git_upload.ps1 -Force -Message "紧急修复"
```

## 配置文件

### 创建配置文件
1. 复制 `git_upload_config_template.json` 为 `git_upload_config.json`
2. 根据需要修改配置项

### 配置项说明
```json
{
  "defaultRemote": "origin",          // 默认远程仓库
  "defaultBranch": "main",            // 默认分支
  "autoCommitMessage": {
    "enabled": true,                   // 启用自动提交信息
    "template": "自动提交 - {timestamp} [{user}@{computer}]"
  },
  "networkCheck": {
    "enabled": true,                   // 启用网络检测
    "timeout": 5000                   // 超时时间（毫秒）
  }
}
```

## 常见问题

### Q: 提示"执行策略"错误怎么办？
A: 以管理员身份运行PowerShell，执行：
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Q: 推送时提示权限错误？
A: 确保已配置Git凭据：
```bash
git config --global user.name "你的用户名"
git config --global user.email "你的邮箱"
```

### Q: 网络连接检测失败？
A: 检查网络连接，或使用 `-Force` 参数跳过网络检测。

### Q: 如何处理合并冲突？
A: 脚本会提示冲突情况，建议先手动解决冲突后再运行脚本。

### Q: 如何回滚错误的提交？
A: 脚本提供自动回滚选项，或手动执行：
```bash
git reset --soft HEAD~1
```

## 安全注意事项

1. **谨慎使用强制推送** - 可能覆盖远程仓库的历史记录
2. **检查提交内容** - 确保不包含敏感信息
3. **备份重要数据** - 推送前建议备份重要文件
4. **权限管理** - 确保只有授权用户可以执行脚本

## 故障排除

### 脚本无法运行
1. 检查PowerShell版本（建议5.0+）
2. 检查执行策略设置
3. 确保Git已正确安装

### 推送失败
1. 检查网络连接
2. 验证远程仓库地址
3. 确认Git凭据配置
4. 检查分支权限

### 性能优化
1. 对于大型仓库，考虑使用 `.gitignore` 排除不必要的文件
2. 定期清理Git历史记录
3. 使用SSH密钥代替HTTPS认证

## 更新日志

### v1.0 (2024-01-20)
- ✅ 初始版本发布
- ✅ 基本的Git操作功能
- ✅ 错误处理和用户界面
- ✅ 配置文件支持
- ✅ 中文界面

## 技术支持

如果遇到问题或有改进建议，请：
1. 检查本文档的常见问题部分
2. 查看脚本输出的错误信息
3. 确保Git和PowerShell环境正确配置

## 许可证

本脚本采用MIT许可证，可自由使用和修改。

---

**注意**: 使用本脚本前，请确保理解Git的基本概念和操作，并在重要项目中谨慎使用。