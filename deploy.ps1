param (
    [string]$SshAlias = "myvps"
)

$REMOTE_DIR = "/opt/knowledge-cabin"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "🚀 开始自动化部署 [Knowledge Cabin] 项目 (PowerShell版)..." -ForegroundColor Cyan
Write-Host "📡 当前目标服务器别名 (SSH_ALIAS): [$SshAlias]" -ForegroundColor Magenta
Write-Host "==========================================" -ForegroundColor Cyan

# 1. 检查本地必要文件
if (-not (Test-Path "main.py") -or -not (Test-Path "renderer.py") -or -not (Test-Path "config.json")) {
    Write-Host "❌ 错误: 本地缺少核心源文件！" -ForegroundColor Red
    Exit
}

# 2. 创建目录
Write-Host "📂 1. 正在服务器上检查并创建目标目录..." -ForegroundColor Yellow
ssh $SshAlias "sudo mkdir -p $REMOTE_DIR && sudo chown -R root:root $REMOTE_DIR"
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ 错误: 无法连接服务器！" -ForegroundColor Red
    Exit
}

# 3. 上传文件
Write-Host "📤 2. 正在上传核心文件至服务器..." -ForegroundColor Yellow
scp main.py renderer.py config.json "${SshAlias}:${REMOTE_DIR}/"
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ 错误: 文件上传失败！" -ForegroundColor Red
    Exit
}

# 4. 环境初始化与定时任务托管 (全面改用安全的单行命令流)
Write-Host "⚙️ 3. 正在服务器上配置 Python 环境与 Cron 定时任务..." -ForegroundColor Yellow

# 🎯 压扁后的纯单行无污染 Linux 命令
$LinuxCmd = "sudo apt update && (sudo apt install python3-requests python3-bs4 python3-lxml python3-feedparser -y || pip3 install requests beautifulsoup4 lxml feedparser --break-system-packages) ; if ! crontab -l 2>/dev/null | grep -q '$REMOTE_DIR' ; then (crontab -l 2>/dev/null; echo '0 * * * * cd $REMOTE_DIR && /usr/bin/python3 main.py > /dev/null 2>&1') | crontab - && echo '✅ Crontab 定时任务已成功托管！' ; else echo 'ℹ️ Crontab 定时任务已存在，无需重复添加。' ; fi"

ssh $SshAlias $LinuxCmd

Write-Host "==========================================" -ForegroundColor Green
Write-Host "🎉 恭喜！项目已完美成功部署至服务器 [$SshAlias] 的 $REMOTE_DIR 目录！" -ForegroundColor Green
Write-Host "🌐 你的自学知识伪装站将在下一个整点开始自动运转。" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
