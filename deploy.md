# Knowledge Cabin - 服务器部署与自动化配置说明

本指南指导如何将本地调通的项目完美移植到你的境外 VPS，并与现有的 Nginx、Sing-box 节点架构打通。

## 🛠️ 第一步：服务器环境准备与代码上传

1. 使用你的快捷连接方式登录服务器：
   ```bash
   ssh myvps
   ```
2. 在服务器上创建一个项目专用目录：
   ```bash
   mkdir -p /root/knowledge-cabin
   ```
3. 将本地调通的 `main.py`、`renderer.py` 和 `config.json` 复制粘贴到服务器该目录下（或者通过 SCP 等工具上传）。
4. 在 VPS 上安装所需的 Python 底层组件：
   ```bash
   apt update && apt install python3-pip -y
   pip3 install requests beautifulsoup4 lxml
   ```

## ⏳ 第二步：配置全天候无人值守定时调度任务

因为我们要配合 `config.json` 里每个目标地址单独配置的“随机时间段段”或“固定小时”策略，我们的服务器定时任务（Cron Job）需要**每小时自动苏醒一次**进行策略匹配与内容清洗。

1. 打开服务器的定时任务编辑面板：
   ```bash
   crontab -e
   ```
2. 在文件末尾添加以下一行规则：
   ```text
   0 * * * * cd /root/knowledge-cabin && /usr/bin/python3 main.py > /dev/null 2>&1
   ```
   _(参数解析：每个整点（如1点、2点、3点）的0分，自动进入目录使用 Python3 执行程序。程序会自动核对当前小时是否符合 config 里的抓取策略。如果符合则爬取，如果不符合则安静跳过。)_

## 🛡️ 第三步：完美契合 Nginx 与客户端

1. **零改动运行**：由于程序中内置了 `output_path="/var/www/html/index.html"`，它会在每个满足策略的小时，全自动覆盖掉原有的 Nginx 目录文件。
2. **流量伪装加分**：此时你通过浏览器访问 `https://yourdomain.com`，看到的将是一个包含 Rust、Flutter 以及全球科技新闻实时自动归类的高级动态站点。任何审查（GFW）对你的 443 端口进行随机抽样探测，都挑不出任何代理特征。
