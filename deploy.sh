#!/bin/bash

# ==================== 配置区域 ====================
# 🎯 定义接收参数，默认值为 "myvps"。在命令行输入时可随时覆盖。
# 🎯 使用你之前在 ~/.ssh/config 里配置好的别名快捷方式
SSH_ALIAS=${1:-"myvps"}

# 🎯 服务器目标运行目录
REMOTE_DIR="/opt/knowledge-cabin"
# ==================================================

echo "=========================================="
echo "🚀 开始自动化部署 [Knowledge Cabin] 项目..."
echo "=========================================="

# 1. 检查本地必要文件是否存在
if [ ! -f "main.py" ] || [ ! -f "renderer.py" ] || [ ! -f "config.json" ]; then
    echo "❌ 错误: 本地缺少核心源文件 (main.py, renderer.py 或 config.json)！"
    exit 1
fi

# 2. 远程连接 VPS，创建 /opt 目标目录并确保赋权
echo "📂 1. 正在服务器上检查并创建目标目录: ${REMOTE_DIR}..."
ssh -t ${SSH_ALIAS} "sudo mkdir -p ${REMOTE_DIR} && sudo chown -R root:root ${REMOTE_DIR}"
if [ $? -ne 0 ]; then
    echo "❌ 错误: 无法在服务器上创建目录，请检查 SSH 连接或权限！"
    exit 1
fi

# 3. 安全上传核心核心程序与配置文件
echo "📤 2. 正在上传核心文件至服务器..."
# 注意：我们不上传本地测试产生的 data_store.json 和测试 index.html，保持服务器环境纯净
scp main.py renderer.py config.json ${SSH_ALIAS}:${REMOTE_DIR}/
if [ $? -ne 0 ]; then
    echo "❌ 错误: 文件上传失败！"
    exit 1
fi

# 4. 在服务器上进行环境初始化与定时任务托管
echo "⚙️ 3. 正在服务器上配置 Python 环境与 Cron 定时任务..."
ssh -t ${SSH_ALIAS} "
    # 安装依赖
    sudo apt update && sudo apt install python3-pip -y
    sudo apt install python3-requests python3-bs4 python3-lxml python3-feedparser -y || pip3 install requests beautifulsoup4 lxml feedparser --break-system-packages
    
    # 智能检查并写入每小时执行一次的 Crontab 任务
    (crontab -l 2>/dev/null | grep -q '${REMOTE_DIR}')
    if [ \$? -ne 0 ]; then
        (crontab -l 2>/dev/null; echo '0 * * * * cd ${REMOTE_DIR} && /usr/bin/python3 main.py > /dev/null 2>&1') | crontab -
        echo '✅ Crontab 定时任务已成功托管！'
    else
        echo 'ℹ️ Crontab 定时任务已存在，无需重复添加。'
    fi
"

echo "=========================================="
echo "🎉 恭喜！项目已完美成功部署至服务器 ${REMOTE_DIR} 目录！"
echo "🌐 你的自学知识伪装站将在下一个整点开始自动运转。"
echo "=========================================="
