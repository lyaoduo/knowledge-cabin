param (
    # 🎯 支持命令行传参，默认值为 myvps
    [string]$SshAlias = "myvps",

    # 可选：自定义服务器部署目录，默认使用当前 SSH 用户家目录下的 knowledge-cabin
    [string]$RemoteDir = ""
)

function Invoke-RemoteBash {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Script,

        [string[]]$Arguments = @()
    )

    $normalizedScript = (($Script -split "`r?`n") -join "`n")
    if (-not $normalizedScript.EndsWith("`n")) {
        $normalizedScript += "`n"
    }

    $startInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $startInfo.FileName = "ssh"
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    $startInfo.RedirectStandardInput = $true
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    $startInfo.ArgumentList.Add($SshAlias)
    $startInfo.ArgumentList.Add("bash")
    $startInfo.ArgumentList.Add("-s")
    $startInfo.ArgumentList.Add("--")

    foreach ($argument in $Arguments) {
        $startInfo.ArgumentList.Add($argument)
    }

    $process = [System.Diagnostics.Process]::new()
    $process.StartInfo = $startInfo
    $process.Start() | Out-Null
    $process.StandardInput.Write($normalizedScript)
    $process.StandardInput.Close()

    $stdout = $process.StandardOutput.ReadToEnd()
    $stderr = $process.StandardError.ReadToEnd()
    $process.WaitForExit()

    $output = if ([string]::IsNullOrWhiteSpace($stdout)) {
        @()
    }
    else {
        @($stdout.TrimEnd("`r", "`n") -split "`r?`n")
    }

    $errorOutput = if ([string]::IsNullOrWhiteSpace($stderr)) {
        @()
    }
    else {
        @($stderr.TrimEnd("`r", "`n") -split "`r?`n")
    }

    [PSCustomObject]@{
        Output      = $output
        ErrorOutput = $errorOutput
        ExitCode    = $process.ExitCode
    }
}

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "🚀 开始自动化部署 [Knowledge Cabin] 项目 ..." -ForegroundColor Cyan
Write-Host "📡 当前目标服务器别名 (SSH_ALIAS): [$SshAlias]" -ForegroundColor Magenta
Write-Host "==========================================" -ForegroundColor Cyan

# 1. 检查本地必要文件
if (-not (Test-Path "main.py") -or -not (Test-Path "renderer.py") -or -not (Test-Path "config.json")) {
    Write-Host "❌ 错误: 本地缺少核心源文件！" -ForegroundColor Red
    exit 1
}

# 2. 远程连接 VPS，解析部署目录并检测是否为首次部署
Write-Host "🔍 1. 正在检查服务器环境状态..." -ForegroundColor Yellow
if ([string]::IsNullOrWhiteSpace($RemoteDir)) {
    $ResolveDir = @'
printf '%s' "$HOME/knowledge-cabin"
'@
    $ResolveResult = Invoke-RemoteBash -Script $ResolveDir
    if ($ResolveResult.ExitCode -ne 0) {
        Write-Host "❌ 错误: 无法连接服务器，请检查 SSH_ALIAS [$SshAlias] 是否正确！" -ForegroundColor Red
        exit 1
    }
    $RemoteDir = (($ResolveResult.Output -join "`n").Trim())
}

if ([string]::IsNullOrWhiteSpace($RemoteDir)) {
    Write-Host "❌ 错误: 无法解析服务器部署目录！" -ForegroundColor Red
    exit 1
}

Write-Host "📁 当前目标部署目录: $RemoteDir" -ForegroundColor DarkCyan

$InspectScript = @'
set -e
REMOTE_DIR="$1"
mkdir -p "$REMOTE_DIR"

if [ -f "$REMOTE_DIR/main.py" ]; then
    echo INCREMENTAL
else
    echo FIRST_TIME
fi
'@

$InspectResult = Invoke-RemoteBash -Script $InspectScript -Arguments @($RemoteDir)
if ($InspectResult.ExitCode -ne 0) {
    Write-Host "❌ 错误: 无法创建服务器目录 [$RemoteDir]，请确认当前 SSH 用户对该路径有写权限。" -ForegroundColor Red
    exit 1
}

$DeployMode = (($InspectResult.Output -join "`n").Trim())

# 3. 安全上传最新的核心程序与配置文件
Write-Host "📤 2. 正在同步核心代码文件至服务器..." -ForegroundColor Yellow
$ScpTarget = "${SshAlias}:${RemoteDir}/"
& scp main.py renderer.py config.json $ScpTarget
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ 错误: 文件上传失败！" -ForegroundColor Red
    exit 1
}

# 4. 智能调度：每次部署都幂等校验运行环境与 Cron，兼容非 root 用户
if ($DeployMode -eq "INCREMENTAL") {
    Write-Host "⚡ 检测到项目已存在，开启「增量更新」模式！" -ForegroundColor Green
}
else {
    Write-Host "🌟 未检测到旧文件，开启「首次部署」完整模式！" -ForegroundColor Blue
}

Write-Host "⚙️ 3. 正在以当前 SSH 用户身份同步 Python 环境与 Cron 定时任务..." -ForegroundColor Yellow

$SetupScript = @'
set -e
REMOTE_DIR="$1"
PACKAGES=(requests beautifulsoup4 lxml feedparser)
SUDO_BIN=""

if command -v sudo >/dev/null 2>&1 && sudo -n true >/dev/null 2>&1; then
    SUDO_BIN="sudo -n"
    echo "ℹ️ 检测到免密 sudo，将优先补齐系统级 Python 依赖。"
fi

PYTHON_BIN="$(command -v python3 || command -v python || true)"

if [ -n "$SUDO_BIN" ] && command -v apt-get >/dev/null 2>&1; then
    NEEDS_SYSTEM_BOOTSTRAP=0
    if [ -z "$PYTHON_BIN" ] || ! "$PYTHON_BIN" -m pip --version >/dev/null 2>&1 || ! "$PYTHON_BIN" -m venv --help >/dev/null 2>&1; then
        NEEDS_SYSTEM_BOOTSTRAP=1
    fi

    if [ "$NEEDS_SYSTEM_BOOTSTRAP" -eq 1 ]; then
        $SUDO_BIN apt-get update
        $SUDO_BIN apt-get install -y python3 python3-pip python3-venv
        PYTHON_BIN="$(command -v python3 || command -v python || true)"
    fi
fi

if [ -z "$PYTHON_BIN" ]; then
    echo "❌ 未找到 python3/python，请先在服务器上安装 Python。"
    exit 1
fi

VENV_DIR="$REMOTE_DIR/.venv"
PYTHON_RUNTIME="$PYTHON_BIN"
LAUNCHER="$REMOTE_DIR/run_knowledge_cabin.sh"
SITE_BUILD_DIR="$REMOTE_DIR/.site"
PUBLISH_DIR="/var/www/html"

if [ ! -x "$VENV_DIR/bin/python" ]; then
    if "$PYTHON_BIN" -m venv "$VENV_DIR" >/dev/null 2>&1; then
        echo "✅ 已创建用户级虚拟环境: $VENV_DIR"
    else
        echo "ℹ️ 当前环境无法创建 venv，回退到 --user 安装依赖。"
    fi
fi

if [ -x "$VENV_DIR/bin/python" ]; then
    "$VENV_DIR/bin/python" -m ensurepip --upgrade >/dev/null 2>&1 || true
fi

if [ -x "$VENV_DIR/bin/python" ] && "$VENV_DIR/bin/python" -m pip --version >/dev/null 2>&1; then
    PYTHON_RUNTIME="$VENV_DIR/bin/python"
    "$PYTHON_RUNTIME" -m pip install --upgrade pip >/dev/null 2>&1 || true
    "$PYTHON_RUNTIME" -m pip install "${PACKAGES[@]}"
else
    if [ -x "$VENV_DIR/bin/python" ]; then
        echo "ℹ️ 检测到不完整的虚拟环境，回退到 --user 安装依赖。"
    fi

    if ! "$PYTHON_BIN" -m pip --version >/dev/null 2>&1; then
        "$PYTHON_BIN" -m ensurepip --upgrade --user >/dev/null 2>&1 || \
            "$PYTHON_BIN" -m ensurepip --upgrade >/dev/null 2>&1 || true
    fi

    if ! "$PYTHON_BIN" -m pip --version >/dev/null 2>&1; then
        GET_PIP="$REMOTE_DIR/.get-pip.py"
        if "$PYTHON_BIN" - "$GET_PIP" <<'PY' >/dev/null 2>&1
import sys
import urllib.request

urllib.request.urlretrieve("https://bootstrap.pypa.io/get-pip.py", sys.argv[1])
PY
        then
            "$PYTHON_BIN" "$GET_PIP" --user >/dev/null 2>&1 || true
            rm -f "$GET_PIP"
        fi
    fi

    if ! "$PYTHON_BIN" -m pip --version >/dev/null 2>&1; then
        echo "❌ 未找到 pip，请先为当前账号安装 pip 或 python3-venv。"
        exit 1
    fi

    "$PYTHON_BIN" -m pip install --user "${PACKAGES[@]}" || \
        "$PYTHON_BIN" -m pip install --user --break-system-packages "${PACKAGES[@]}"
fi

cat > "$LAUNCHER" <<'EOF'
#!/usr/bin/env bash
set -e
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON_BIN="__PYTHON_RUNTIME__"
SITE_BUILD_DIR="$PROJECT_DIR/.site"
PUBLISH_DIR="/var/www/html"

mkdir -p "$SITE_BUILD_DIR"
cd "$PROJECT_DIR"
KNOWLEDGE_CABIN_OUTPUT_PATH="$SITE_BUILD_DIR/index.html" "$PYTHON_BIN" main.py "$@"

if command -v sudo >/dev/null 2>&1 && sudo -n true >/dev/null 2>&1; then
    sudo -n mkdir -p "$PUBLISH_DIR"
    if command -v rsync >/dev/null 2>&1; then
        sudo -n rsync -a --delete "$SITE_BUILD_DIR/" "$PUBLISH_DIR/"
    else
        sudo -n rm -f "$PUBLISH_DIR/index.html"
        sudo -n rm -rf "$PUBLISH_DIR/articles" "$PUBLISH_DIR/media"
        if [ -f "$SITE_BUILD_DIR/index.html" ]; then
            sudo -n install -m 644 "$SITE_BUILD_DIR/index.html" "$PUBLISH_DIR/index.html"
        fi
        if [ -d "$SITE_BUILD_DIR/articles" ]; then
            sudo -n cp -a "$SITE_BUILD_DIR/articles" "$PUBLISH_DIR/"
        fi
        if [ -d "$SITE_BUILD_DIR/media" ]; then
            sudo -n cp -a "$SITE_BUILD_DIR/media" "$PUBLISH_DIR/"
        fi
    fi
    echo "✅ 已通过 sudo 同步静态文件到: $PUBLISH_DIR"
else
    echo "ℹ️ 未检测到免密 sudo，静态文件保留在: $SITE_BUILD_DIR"
fi
EOF

sed -i "s|__PYTHON_RUNTIME__|$PYTHON_RUNTIME|" "$LAUNCHER"
chmod +x "$LAUNCHER"
echo "✅ 已更新项目启动器: $LAUNCHER"

if command -v crontab >/dev/null 2>&1; then
    CRON_LINE="0 * * * * $LAUNCHER > /dev/null 2>&1"
    EXISTING_CRONTAB="$(crontab -l 2>/dev/null || true)"

    if printf '%s\n' "$EXISTING_CRONTAB" | grep -F "$LAUNCHER" >/dev/null; then
        echo "ℹ️ Crontab 定时任务已存在，无需重复添加。"
    else
        {
            printf '%s\n' "$EXISTING_CRONTAB"
            printf '%s\n' "$CRON_LINE"
        } | sed '/^[[:space:]]*$/d' | crontab -
        echo "✅ Crontab 定时任务已成功托管！"
    fi
else
    echo "⚠️ 未找到 crontab，已跳过定时任务配置。"
fi

echo "✅ 当前运行解释器: $PYTHON_RUNTIME"
'@

$SetupResult = Invoke-RemoteBash -Script $SetupScript -Arguments @($RemoteDir)
if ($SetupResult.ExitCode -ne 0) {
    $SetupResult.Output | ForEach-Object { Write-Host $_ }
    $SetupResult.ErrorOutput | ForEach-Object { Write-Host $_ }
    Write-Host "❌ 错误: 服务器环境初始化失败，请根据上面的日志修复后重试。" -ForegroundColor Red
    exit 1
}

$SetupResult.Output | ForEach-Object { Write-Host $_ }
$SetupResult.ErrorOutput | ForEach-Object { Write-Host $_ }

Write-Host "==========================================" -ForegroundColor Green
Write-Host "🎉 恭喜！项目已成功同步至服务器 [$SshAlias] 的 $RemoteDir 目录！" -ForegroundColor Green
Write-Host "ℹ️ 运行时会先渲染到 $RemoteDir/.site，再自动通过 sudo 同步到 /var/www/html。" -ForegroundColor Gray
Write-Host "ℹ️ 可在服务器上执行: $RemoteDir/run_knowledge_cabin.sh --force-run" -ForegroundColor Gray
Write-Host "==========================================" -ForegroundColor Green
