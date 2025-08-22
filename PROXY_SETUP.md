# Git上传脚本代理配置说明

## 概述

本脚本已集成HTTP代理支持，默认使用端口4780进行所有Git HTTP/HTTPS通信。这确保了在网络环境受限的情况下，脚本仍能正常连接到GitHub等远程仓库。

## 代理配置

### 默认设置
- **代理地址**: `http://127.0.0.1:4780`
- **支持协议**: HTTP 和 HTTPS
- **自动配置**: 脚本启动时自动配置Git代理设置

### 自定义代理端口

如果您的代理服务运行在不同端口，可以使用 `-ProxyPort` 参数：

```powershell
# 使用8080端口
.\git_upload.ps1 -ProxyPort 8080

# 使用3128端口
.\git_upload.ps1 -ProxyPort 3128 -Message "通过自定义代理提交"
```

### 网络连接逻辑

脚本采用智能网络连接策略：

1. **直连测试**: 首先尝试直接连接GitHub (端口443)
2. **代理回退**: 如果直连失败，自动配置并使用代理
3. **配置持久化**: 代理设置会保存到Git全局配置中

### 配置文件支持

配置模板文件 `git_upload_config_template.json` 已更新，包含代理设置：

```json
{
  "proxy": {
    "enabled": true,
    "port": "4780",
    "host": "127.0.0.1",
    "autoDetect": true
  }
}
```

## 使用示例

### 基本使用（使用默认代理）
```powershell
.\git_upload.ps1
```

### 指定提交信息和代理端口
```powershell
.\git_upload.ps1 -Message "修复网络连接问题" -ProxyPort 4780
```

### 强制推送（谨慎使用）
```powershell
.\git_upload.ps1 -Force -ProxyPort 4780
```

## 故障排除

### 检查当前代理配置
```powershell
git config --list | Select-String -Pattern "proxy"
```

### 手动清除代理配置
```powershell
git config --global --unset http.proxy
git config --global --unset https.proxy
```

### 测试网络连接
```powershell
Test-NetConnection github.com -Port 443
```

## 注意事项

1. **代理服务**: 确保本地代理服务正在运行并监听指定端口
2. **防火墙**: 检查防火墙设置，确保代理端口未被阻止
3. **全局配置**: 脚本会修改Git的全局代理配置，影响所有Git操作
4. **安全性**: 仅在受信任的网络环境中使用代理

## 更新日志

- **v1.1**: 集成HTTP代理支持，默认端口4780
- **v1.0**: 基础Git上传功能