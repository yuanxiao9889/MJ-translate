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
echo "           Git 拉取脚本"
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

# 显示远程仓库信息
print_info "远程仓库信息："
git remote -v
echo

# 检查本地是否有未提交的更改
changes=$(git status --porcelain | wc -l)
stashed=false

if [ $changes -gt 0 ]; then
    print_warning "发现 $changes 个未提交的更改："
    git status --short
    echo
    
    read -p "是否暂存这些更改？(y/n，默认y): " stash_changes
    stash_changes=${stash_changes:-y}
    
    if [[ $stash_changes =~ ^[Yy]$ ]]; then
        print_info "暂存本地更改..."
        if ! git stash push -m "自动暂存 - $(date)"; then
            print_error "暂存失败！"
            exit 1
        fi
        stashed=true
    else
        print_warning "继续拉取可能会导致冲突。"
        read -p "确定要继续吗？(y/n，默认n): " continue_pull
        continue_pull=${continue_pull:-n}
        
        if [[ $continue_pull =~ ^[Nn]$ ]]; then
            print_info "操作已取消。"
            exit 0
        fi
    fi
    echo
fi

# 获取远程更新信息
print_info "获取远程仓库信息..."
if ! git fetch origin; then
    print_error "获取远程信息失败！"
    exit 1
fi

# 检查是否有远程更新
behind=$(git rev-list HEAD..origin/$current_branch --count 2>/dev/null || echo "0")
ahead=$(git rev-list origin/$current_branch..HEAD --count 2>/dev/null || echo "0")

if [ $behind -eq 0 ]; then
    print_info "本地代码已是最新版本。"
    if [ $ahead -gt 0 ]; then
        print_info "本地有 $ahead 个提交领先于远程。"
    fi
    # 跳转到恢复暂存部分
    restore_stash=true
else
    print_info "远程有 $behind 个新提交。"
    if [ $ahead -gt 0 ]; then
        print_info "本地有 $ahead 个提交领先于远程。"
    fi
    echo
    
    # 显示即将拉取的提交
    print_info "即将拉取的提交："
    git log --oneline HEAD..origin/$current_branch --max-count=10
    echo
    
    # 执行拉取
    print_info "拉取远程更改..."
    if [ $ahead -gt 0 ]; then
        print_info "使用rebase模式拉取以保持提交历史整洁..."
        pull_cmd="git pull --rebase origin $current_branch"
    else
        pull_cmd="git pull origin $current_branch"
    fi
    
    if ! eval $pull_cmd; then
        print_error "拉取失败！"
        print_info "可能存在冲突需要手动解决。"
        echo
        print_info "冲突解决步骤："
        echo "1. 编辑冲突文件，解决冲突标记"
        echo "2. 运行: git add <冲突文件>"
        if [ $ahead -gt 0 ]; then
            echo "3. 运行: git rebase --continue"
        else
            echo "3. 运行: git commit"
        fi
        exit 1
    fi
fi

# 恢复暂存的更改
if [ "$stashed" = true ]; then
    print_info "恢复之前暂存的更改..."
    if ! git stash pop; then
        print_warning "恢复暂存更改时出现冲突！"
        print_info "请手动解决冲突后运行: git stash drop"
    else
        print_success "暂存的更改已成功恢复。"
    fi
    echo
fi

echo "========================================"
echo "           拉取完成！"
echo "========================================"
print_success "代码已成功从远程仓库拉取。"
print_info "分支: $current_branch"
echo

# 显示最新的几个提交
print_info "最新提交记录："
git log --oneline --max-count=5
echo

# 在非交互模式下不暂停
if [ -t 0 ]; then
    read -p "按任意键继续..."
fi