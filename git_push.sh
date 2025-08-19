#!/bin/bash

# 设置颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 打印带颜色的消息
print_info() {
    echo -e "${BLUE}[信息]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[成功]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[警告]${NC} $1"
}

print_error() {
    echo -e "${RED}[错误]${NC} $1"
}

echo "========================================"
echo "           Git 推送脚本"
echo "========================================"
echo

# 检查是否在Git仓库中
if [ ! -d ".git" ]; then
    print_error "当前目录不是Git仓库！"
    print_info "请在Git仓库根目录下运行此脚本。"
    exit 1
fi

# 检查Git是否安装
if ! command -v git &> /dev/null; then
    print_error "Git未安装！"
    print_info "请先安装Git: https://git-scm.com/"
    exit 1
fi

# 显示当前状态
print_info "检查当前Git状态..."
if ! git status --porcelain &> /dev/null; then
    print_error "无法获取Git状态！"
    exit 1
fi

# 检查是否有未提交的更改
changes=$(git status --porcelain | wc -l)
if [ $changes -eq 0 ]; then
    print_info "没有需要提交的更改。"
    echo
    # 跳转到推送部分
    push_only=true
else
    echo
    print_info "发现 $changes 个文件有更改。"
    echo
    
    # 显示更改的文件
    print_info "更改的文件列表："
    git status --short
    echo
    
    # 询问是否添加所有文件
    read -p "是否添加所有更改的文件？(y/n，默认y): " add_all
    add_all=${add_all:-y}
    
    if [[ $add_all =~ ^[Nn]$ ]]; then
        print_info "请手动添加需要提交的文件，然后重新运行此脚本。"
        exit 0
    fi
    
    # 添加所有更改
    print_info "添加所有更改到暂存区..."
    if ! git add .; then
        print_error "添加文件失败！"
        exit 1
    fi
    
    # 获取提交信息
    read -p "请输入提交信息（默认：更新代码）: " commit_msg
    commit_msg=${commit_msg:-"更新代码"}
    
    # 提交更改
    print_info "提交更改..."
    if ! git commit -m "$commit_msg"; then
        print_error "提交失败！"
        exit 1
    fi
fi

# 获取当前分支
current_branch=$(git branch --show-current)
if [ -z "$current_branch" ]; then
    print_error "无法获取当前分支！"
    exit 1
fi

print_info "当前分支: $current_branch"
echo

# 检查远程仓库
if ! git remote -v &> /dev/null; then
    print_error "没有配置远程仓库！"
    print_info "请先添加远程仓库: git remote add origin <仓库URL>"
    exit 1
fi

# 尝试推送
print_info "推送到远程仓库..."
if ! git push origin "$current_branch"; then
    echo
    print_warning "推送失败，可能需要先拉取远程更改。"
    print_info "尝试拉取远程更改..."
    
    if ! git pull origin "$current_branch"; then
        print_error "拉取失败！可能存在冲突需要手动解决。"
        print_info "请手动解决冲突后重新运行此脚本。"
        exit 1
    fi
    
    print_info "拉取成功，重新尝试推送..."
    if ! git push origin "$current_branch"; then
        print_error "推送仍然失败！"
        exit 1
    fi
fi

echo
echo "========================================"
echo "           推送成功！"
echo "========================================"
print_success "代码已成功推送到远程仓库。"
print_info "分支: $current_branch"
echo

# 在非交互模式下不暂停
if [ -t 0 ]; then
    read -p "按任意键继续..."
fi