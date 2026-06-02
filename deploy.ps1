param (
    # 🎯 支持命令行传参，默认值为 myvps
    [string]$SshAlias = "myvps"
)

$REMOTE_DIR = "/opt/knowledge-cabin"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "🚀 开始自动化部署 [Knowledge Cabin] 项目 ..." -ForegroundColor Cyan
Write-Host "📡 当前目标服务器别名 (SSH_ALIAS): [$SshAlias]" -ForegroundColor Magenta
Write-Host "==========================================" -ForegroundColor Cyan

# 1. 检查本地必要文件
if (-not (Test-Path "main.py") -or -not (Test-Path "renderer.py") -or -not (Test-Path "config.json")) {
    Write-Host "❌ 错误: 本地缺少核心源文件！" -ForegroundColor Red
    Exit
}

# 2. 远程连接 VPS，智能检测是否为首次部署
Write-Host "🔍 1. 正在检查服务器环境状态..." -ForegroundColor Yellow
ssh $SshAlias "if [ -f '$REMOTE_DIR/main.py' ]; then echo 'INCREMENTAL'; else echo 'FIRST_TIME'; fi" | Set-Variable -Name DeployMode

# 预创建目录并确保归属权
ssh $SshAlias "sudo mkdir -p $REMOTE_DIR && sudo chown -R root:root $REMOTE_DIR"

# 3. 安全上传最新的核心程序与配置文件
Write-Host "📤 2. 正在同步核心代码文件至服务器..." -ForegroundColor Yellow
scp main.py renderer.py config.json "${SshAlias}:${REMOTE_DIR}/"
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ 错误: 文件上传失败！" -ForegroundColor Red
    Exit
}

# 4. 智能调度：根据环境状态决定是否执行环境重构
if ($DeployMode -eq "INCREMENTAL") {
    Write-Host "⚡ 检测到项目已存在，开启「增量更新」模式！" -ForegroundColor Green
    Write-Host "ℹ️ 自动跳过环境依赖检查与 Crontab 配置，文件已覆盖完成。" -ForegroundColor Gray
}
else {
    Write-Host "🌟 未检测到旧文件，开启「首次部署」完整模式！" -ForegroundColor Blue
    Write-Host "⚙️ 3. 正在服务器上配置 Python 环境与 Cron 定时任务 (单行流模式)..." -ForegroundColor Yellow

    # 包含：适配新版系统的组件包安装、无污染 Cron 挂载
    $LinuxCmd = "sudo apt update && (sudo apt install python3-requests python3-bs4 python3-lxml python3-feedparser -y || pip3 install requests beautifulsoup4 lxml feedparser --break-system-packages) ; if ! crontab -l 2>/dev/null | grep -q '$REMOTE_DIR' ; then (crontab -l 2>/dev/null; echo '0 * * * * cd $REMOTE_DIR && /usr/bin/python3 main.py > /dev/null 2>&1') | crontab - && echo '✅ Crontab 定时任务已成功托管！' ; else echo 'ℹ️ Crontab 定时任务已存在，无需重复添加。' ; fi"
    
    ssh $SshAlias $LinuxCmd
}

Write-Host "==========================================" -ForegroundColor Green
Write-Host "🎉 恭喜！项目已成功同步至服务器 [$SshAlias] 的 $REMOTE_DIR 目录！" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
