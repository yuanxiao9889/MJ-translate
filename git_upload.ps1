# GitHub Auto Upload Script
# Author: AI Assistant
# Version: 1.0
# Platform: Windows PowerShell

param(
    [string]$Message = "",
    [string]$Remote = "origin",
    [string]$Branch = "",
    [switch]$Help,
    [switch]$Config,
    [switch]$Force
)

# Set console encoding
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# Config file path
$ConfigFile = "$PSScriptRoot\git_upload_config.json"

# Color output function
function Write-ColorOutput {
    param(
        [string]$Message,
        [string]$Color = "White"
    )
    Write-Host $Message -ForegroundColor $Color
}

# Show help information
function Show-Help {
    Write-ColorOutput "=== GitHub Auto Upload Script Help ===" "Cyan"
    Write-ColorOutput ""
    Write-ColorOutput "Usage:" "Yellow"
    Write-ColorOutput "  .\git_upload.ps1 [parameters]" "White"
    Write-ColorOutput ""
    Write-ColorOutput "Parameters:" "Yellow"
    Write-ColorOutput "  -Message [string]    Custom commit message" "White"
    Write-ColorOutput "  -Remote [string]     Remote repository name (default: origin)" "White"
    Write-ColorOutput "  -Branch [string]     Target branch (default: current branch)" "White"
    Write-ColorOutput "  -Help               Show this help information" "White"
    Write-ColorOutput "  -Config             Configure remote repository" "White"
    Write-ColorOutput "  -Force              Force push (use with caution)" "White"
    Write-ColorOutput ""
    Write-ColorOutput "Examples:" "Yellow"
    Write-ColorOutput "  .\git_upload.ps1" "Green"
    Write-ColorOutput "  .\git_upload.ps1 -Message 'Fix bug'" "Green"
    Write-ColorOutput "  .\git_upload.ps1 -Remote upstream -Branch develop" "Green"
    Write-ColorOutput ""
}

# Configure remote repository
function Set-GitConfig {
    Write-ColorOutput "=== Git Repository Configuration ===" "Cyan"
    
    # Get current remote repository information
    $remotes = git remote -v 2>$null
    if ($remotes) {
        Write-ColorOutput "Current remote repositories:" "Yellow"
        $remotes | ForEach-Object { Write-ColorOutput "  $_" "White" }
        Write-ColorOutput ""
    }
    
    $remoteUrl = Read-Host "Enter remote repository URL (leave empty to keep current)"
    if ($remoteUrl) {
        git remote set-url origin $remoteUrl
        if ($LASTEXITCODE -eq 0) {
            Write-ColorOutput "Remote repository URL updated" "Green"
        } else {
            Write-ColorOutput "Failed to update remote repository URL" "Red"
        }
    }
    
    # Save configuration
    $config = @{
        "lastUpdate" = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
        "defaultRemote" = $Remote
        "defaultBranch" = $Branch
    }
    
    $config | ConvertTo-Json | Set-Content -Path $ConfigFile -Encoding UTF8
    Write-ColorOutput "Configuration saved" "Green"
}

# Test Git environment
function Test-GitEnvironment {
    Write-ColorOutput "Testing Git environment..." "Yellow"
    
    # Check if Git is installed
    $gitVersion = git --version 2>$null
    if (-not $gitVersion) {
        Write-ColorOutput "Git is not installed or not in PATH" "Red"
        Write-ColorOutput "Please ensure Git is properly installed and added to system PATH" "Red"
        return $false
    }
    Write-ColorOutput "Git installed: $gitVersion" "Green"
    
    # Check if current directory is a Git repository
    if (-not (Test-Path ".git")) {
        Write-ColorOutput "Current directory is not a Git repository" "Red"
        $init = Read-Host "Initialize as Git repository? (y/N)"
        if ($init -eq "y" -or $init -eq "Y") {
            git init
            if ($LASTEXITCODE -eq 0) {
                Write-ColorOutput "Git repository initialized successfully" "Green"
            } else {
                Write-ColorOutput "Failed to initialize Git repository" "Red"
                return $false
            }
        } else {
            return $false
        }
    } else {
        Write-ColorOutput "Current directory is a Git repository" "Green"
    }
    
    return $true
}

# Test network connection
function Test-NetworkConnection {
    param([string]$RemoteUrl)
    
    Write-ColorOutput "Testing network connection..." "Yellow"
    
    if ($RemoteUrl -match "github\.com|gitlab\.com|bitbucket\.org") {
        $testResult = Test-NetConnection -ComputerName "github.com" -Port 443 -InformationLevel Quiet -WarningAction SilentlyContinue
        if ($testResult) {
            Write-ColorOutput "Network connection is normal" "Green"
            return $true
        } else {
            Write-ColorOutput "Cannot connect to remote repository" "Red"
            return $false
        }
    }
    
    Write-ColorOutput "Skip network connection test" "Yellow"
    return $true
}

# Get Git status
function Get-GitStatus {
    Write-ColorOutput "Checking Git status..." "Yellow"
    
    $status = git status --porcelain 2>$null
    $ahead = 0
    $behind = 0
    
    # Try to get ahead/behind information
    $branchInfo = git status -b --porcelain 2>$null | Select-Object -First 1
    if ($branchInfo -match "ahead (\d+)") {
        $ahead = [int]$matches[1]
    }
    if ($branchInfo -match "behind (\d+)") {
        $behind = [int]$matches[1]
    }
    
    if ($status) {
        Write-ColorOutput "Found the following changes:" "Yellow"
        $status | ForEach-Object {
            $statusCode = $_.Substring(0, 2).Trim()
            $fileName = $_.Substring(3)
            $statusText = switch ($statusCode) {
                "M" { "Modified" }
                "A" { "Added" }
                "D" { "Deleted" }
                "R" { "Renamed" }
                "C" { "Copied" }
                "??" { "Untracked" }
                default { "Unknown" }
            }
            Write-ColorOutput "  [$statusText] $fileName" "White"
        }
    } else {
        Write-ColorOutput "Working directory is clean, no changes" "Green"
    }
    
    if ($ahead -gt 0) {
        Write-ColorOutput "Local is ahead of remote by $ahead commits" "Yellow"
    }
    
    if ($behind -gt 0) {
        Write-ColorOutput "Local is behind remote by $behind commits" "Yellow"
    }
    
    return @{
        "HasChanges" = [bool]$status
        "Ahead" = $ahead
        "Behind" = $behind
        "Changes" = $status
    }
}

# Generate commit message
function New-CommitMessage {
    param([string]$CustomMessage)
    
    if ($CustomMessage) {
        return $CustomMessage
    }
    
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $hostname = $env:COMPUTERNAME
    $username = $env:USERNAME
    
    return "Auto commit - $timestamp [$username@$hostname]"
}

# Execute Git operations
function Invoke-GitUpload {
    param(
        [string]$CommitMessage,
        [string]$RemoteName,
        [string]$BranchName,
        [bool]$ForceMode
    )
    
    # Add all changes
    Write-ColorOutput "Adding changed files..." "Yellow"
    git add .
    if ($LASTEXITCODE -ne 0) {
        Write-ColorOutput "Failed to add files" "Red"
        return $false
    }
    Write-ColorOutput "Files added successfully" "Green"
    
    # Commit changes
    Write-ColorOutput "Committing changes..." "Yellow"
    git commit -m $CommitMessage
    if ($LASTEXITCODE -ne 0) {
        Write-ColorOutput "No new changes to commit" "Yellow"
    } else {
        Write-ColorOutput "Commit successful: $CommitMessage" "Green"
    }
    
    # Push to remote repository
    Write-ColorOutput "Pushing to remote repository..." "Yellow"
    
    $pushCmd = "git push $RemoteName"
    if ($BranchName) {
        $pushCmd += " $BranchName"
    }
    if ($ForceMode) {
        $pushCmd += " --force"
        Write-ColorOutput "Using force push mode" "Yellow"
    }
    
    Invoke-Expression $pushCmd
    if ($LASTEXITCODE -eq 0) {
        Write-ColorOutput "Push successful" "Green"
    } else {
        Write-ColorOutput "Push failed" "Red"
        
        # Provide rollback option
        $rollback = Read-Host "Rollback last commit? (y/N)"
        if ($rollback -eq "y" -or $rollback -eq "Y") {
            git reset --soft HEAD~1
            if ($LASTEXITCODE -eq 0) {
                Write-ColorOutput "Last commit rolled back" "Green"
            } else {
                Write-ColorOutput "Rollback failed" "Red"
            }
        }
        return $false
    }
    
    return $true
}

# Main function
function Main {
    Write-ColorOutput "=== GitHub Auto Upload Script ===" "Cyan"
    Write-ColorOutput "Current directory: $(Get-Location)" "Gray"
    Write-ColorOutput ""
    
    # Show help
    if ($Help) {
        Show-Help
        return
    }
    
    # Configuration mode
    if ($Config) {
        Set-GitConfig
        return
    }
    
    # Test Git environment
    if (-not (Test-GitEnvironment)) {
        Write-ColorOutput "Environment test failed, script exiting" "Red"
        return
    }
    
    # Get current branch
    if (-not $Branch) {
        $Branch = git branch --show-current 2>$null
        if (-not $Branch) {
            $Branch = "main"
        }
    }
    
    Write-ColorOutput "Target branch: $Branch" "Cyan"
    Write-ColorOutput "Remote repository: $Remote" "Cyan"
    Write-ColorOutput ""
    
    # Get remote repository URL
    $remoteUrl = git remote get-url $Remote 2>$null
    if ($remoteUrl) {
        Write-ColorOutput "Remote repository URL: $remoteUrl" "Cyan"
        
        # Test network connection
        if (-not (Test-NetworkConnection -RemoteUrl $remoteUrl)) {
            $continue = Read-Host "Network connection abnormal, continue? (y/N)"
            if ($continue -ne "y" -and $continue -ne "Y") {
                return
            }
        }
    } else {
        Write-ColorOutput "Cannot get remote repository information" "Yellow"
    }
    
    # Check Git status
    $gitStatus = Get-GitStatus
    if (-not $gitStatus) {
        Write-ColorOutput "Failed to get Git status" "Red"
        return
    }
    
    Write-ColorOutput ""
    
    # Handle conflict prompts
    if ($gitStatus.Behind -gt 0) {
        Write-ColorOutput "Detected new commits in remote repository, recommend pulling updates first" "Yellow"
        $pull = Read-Host "Pull remote updates first? (Y/n)"
        if ($pull -ne "n" -and $pull -ne "N") {
            Write-ColorOutput "Pulling remote updates..." "Yellow"
            git pull $Remote $Branch
            if ($LASTEXITCODE -eq 0) {
                Write-ColorOutput "Pull successful" "Green"
            } else {
                Write-ColorOutput "Pull failed, conflicts may exist" "Red"
                Write-ColorOutput "Please resolve conflicts manually and run script again" "Red"
                return
            }
        }
    }
    
    # If no changes and not force mode, ask whether to continue
    if (-not $gitStatus.HasChanges -and -not $Force) {
        $continue = Read-Host "No changes detected, still want to push? (y/N)"
        if ($continue -ne "y" -and $continue -ne "Y") {
            Write-ColorOutput "Operation cancelled" "Yellow"
            return
        }
    }
    
    # Generate commit message
    $commitMessage = New-CommitMessage -CustomMessage $Message
    Write-ColorOutput "Commit message: $commitMessage" "Cyan"
    
    # Confirm execution
    if (-not $Force) {
        Write-ColorOutput ""
        $confirm = Read-Host "Confirm upload operation? (Y/n)"
        if ($confirm -eq "n" -or $confirm -eq "N") {
            Write-ColorOutput "Operation cancelled" "Yellow"
            return
        }
    }
    
    Write-ColorOutput ""
    Write-ColorOutput "=== Starting upload operation ===" "Cyan"
    
    # Execute upload
    $success = Invoke-GitUpload -CommitMessage $commitMessage -RemoteName $Remote -BranchName $Branch -ForceMode $Force
    
    Write-ColorOutput ""
    if ($success) {
        Write-ColorOutput "=== Upload completed ===" "Green"
        Write-ColorOutput "All operations completed successfully" "Green"
    } else {
        Write-ColorOutput "=== Upload failed ===" "Red"
        Write-ColorOutput "Errors occurred during operation" "Red"
    }
}

# Execute main function
Main

# Pause to view results
if (-not $Help -and -not $Config) {
    Write-ColorOutput ""
    Write-Host "Press any key to exit..." -ForegroundColor Gray
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
}