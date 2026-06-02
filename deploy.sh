#!/bin/bash

# ==================== 动态参数接收 ====================
# 🎯 接收命令行第一个参数，若空则默认为 "myvps"
SSH_ALIAS=${1:-"myvps"}

# 服务器目标运行目录
REMOTE_DIR="/opt/knowledge-cabin"
# =====================================================

echo "=========================================="
echo "🚀 开始自动化部署 [Knowledge Cabin] 项目 ..."
echo "📡 当前目标服务器别名 (SSH_ALIAS): [${SSH_ALIAS}]"
echo "=========================================="

# 1. 检查本地必要文件是否存在
if [ ! -f "main.py" ] || [ ! -f "renderer.py" ] || [ ! -f "config.json" ]; then
    echo "❌ 错误: 本地缺少核心源文件 (main.py, renderer.py 或 config.json)！"
    exit 1
fi

# 2. 远程连接 VPS，智能检测是否为首次部署并创建目录
echo "🔍 1. 正在检查服务器环境状态..."
DEPLOY_MODE=$(ssh ${SSH_ALIAS} "if [ -f '${REMOTE_DIR}/main.py' ]; then echo 'INCREMENTAL'; else echo 'FIRST_TIME'; fi")

ssh ${SSH_ALIAS} "sudo mkdir -p ${REMOTE_DIR} && sudo chown -R root:root ${REMOTE_DIR}"
if [ $? -ne 0 ]; then
    echo "❌ 错误: 无法连接服务器或创建目录，请检查 SSH_ALIAS [${SSH_ALIAS}] 是否正确！"
    exit 1
fi

# 3. 安全上传最新的核心程序与配置文件
echo "📤 2. 正在同步核心代码文件至服务器..."
scp main.py renderer.py config.json ${SSH_ALIAS}:${REMOTE_DIR}/
if [ $? -ne 0 ]; then
    echo "❌ 错误: 文件上传失败！"
    exit 1
fi

# 4. 智能调度：根据环境状态决定是否跳过环境重构
if [ "${DEPLOY_MODE}" = "INCREMENTAL" ]; then
    echo -e "\n⚡ 检测到项目已存在，开启「增量更新」模式！"
    echo "ℹ️ 自动跳过环境依赖检查与 Crontab 配置，文件已覆盖完成。"
else
    echo -e "\n🌟 未检测到旧文件，开启「首次部署」完整模式！"
    echo "⚙️ 3. 正在服务器上配置 Python 环境与 Cron 定时任务..."
    
    # 压扁的单行命令，完美适配新版系统的组件包安装，且无换行符污染风险
    LINUX_CMD="sudo apt update && (sudo apt install python3-requests python3-bs4 python3-lxml python3-feedparser -y || pip3 install requests beautifulsoup4 lxml feedparser --break-system-packages 2>/dev/null) ; if ! crontab -l 2>/dev/null | grep -q '${REMOTE_DIR}' ; then (crontab -l 2>/dev/null; echo '0 * * * * cd ${REMOTE_DIR} && /usr/bin/python3 main.py > /dev/null 2>&1') | crontab - && echo '✅ Crontab 定时任务已成功托管！' ; else echo 'ℹ️ Crontab 定时任务已存在，无需重复添加。' ; fi"
    
    ssh ${SSH_ALIAS} "${LINUX_CMD}"
fi

echo "=========================================="
echo "🎉 恭喜！项目已成功同步至服务器 [${SSH_ALIAS}] 的 ${REMOTE_DIR} 目录！"
echo "=========================================="
