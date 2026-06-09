# Knowledge Cabin - 服务器部署与自动化配置说明

本指南指导如何将本地调通的项目完美移植到你的境外 VPS，并与现有的 Nginx、Sing-box 节点架构打通。

## 🛠️ 第一步：服务器环境准备与代码上传

1. 使用你的快捷连接方式登录服务器：
   ```bash
   ssh myvps
   ```
2. 推荐使用当前 SSH 用户自己的目录进行部署，例如：
   ```bash
   mkdir -p $HOME/knowledge-cabin
   ```
3. 将本地调通的 `main.py`、`renderer.py` 和 `config.json` 复制粘贴到服务器该目录下（或者通过 SCP 等工具上传）。

   ```bash
   # 1. 赋予部署脚本可执行权限（仅需执行一次）
   chmod +x deploy.sh

   # 2. 运行一键部署（默认部署到 $HOME/knowledge-cabin）
   ./deploy.sh your-ssh-alias

   # 3. 如需自定义部署目录，可追加第二个参数
   ./deploy.sh your-ssh-alias /srv/knowledge-cabin
   ```

   windows 用户可以直接在 PowerShell 中使用以下命令上传文件：

   ```powershell
   # 1. 赋予部署脚本可执行权限（仅需执行一次）
   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process

   # 2. 运行一键部署（默认部署到远端用户家目录）
   .\deploy.ps1 -SshAlias your-ssh-alias

   # 3. 如需自定义部署目录
   .\deploy.ps1 -SshAlias your-ssh-alias -RemoteDir /srv/knowledge-cabin

   ```

4. 确保 VPS 至少已安装 `python3`。如果远端账号支持免密 `sudo`，部署脚本会优先使用 `sudo -n apt-get install python3 python3-pip python3-venv` 自动补齐系统依赖；否则会继续走非 root 流程，优先为当前用户创建 `.venv`，并在无法创建虚拟环境时回退到 `pip --user` 安装依赖。

   如果你想手动检查环境，可以执行：

   ```bash
   python3 --version
   ```

   _（如果你使用了部署脚本，则通常不需要手工安装依赖。）_

## ⏳ 第二步：配置全天候无人值守定时调度任务

_（部署脚本中已包含自动配置定时任务的命令，如果你使用了部署脚本则可以跳过这一步）_

因为我们要配合 `config.json` 里每个目标地址单独配置的“随机时间段段”或“固定小时”策略，我们的服务器定时任务（Cron Job）需要**每小时自动苏醒一次**进行策略匹配与内容清洗。

1. 打开服务器的定时任务编辑面板：
   ```bash
   crontab -e
   ```
2. 在文件末尾添加以下一行规则（路径按你的实际部署目录调整）：
   ```text
   0 * * * * /home/your-user/knowledge-cabin/run_knowledge_cabin.sh > /dev/null 2>&1
   ```
   _(参数解析：每个整点（如1点、2点、3点）的 0 分，自动执行部署脚本生成的启动器。启动器会优先使用项目目录下的 `.venv/bin/python`，找不到时再回退到系统 `python3`。程序会自动核对当前小时是否符合 config 里的抓取策略。如果符合则爬取，如果不符合则安静跳过。)_

## 🛡️ 第三步：完美契合 Nginx 与客户端

1. **自动发布到 Web 根目录**：部署脚本生成的启动器会先把页面渲染到项目目录下的 `.site/` staging 目录，然后在检测到免密 `sudo` 时，自动把 `.site/` 同步到 `/var/www/html/`。
2. **非 root 仍负责抓取与渲染**：抓取 RSS、下载图片、清洗正文仍由普通用户执行，只有最终发布到 `/var/www/html/` 这一步会使用 `sudo -n`。这样既满足 Nginx 默认目录，又避免把整套抓取流程长期放在 root 身份下运行。
3. **流量伪装加分**：此时你通过浏览器访问 `https://yourdomain.com`，看到的将是一个包含 Rust、Flutter 以及全球科技新闻实时自动归类的高级动态站点。任何审查（GFW）对你的 443 端口进行随机抽样探测，都挑不出任何代理特征。

## 手动强制执行一次

如果你不想等到下一个整点来验证部署效果，可以直接在服务器上执行以下命令，强制程序立即运行一次：

```bash
$HOME/knowledge-cabin/run_knowledge_cabin.sh --force-run
```

如果你部署到了自定义目录，请将上面的路径替换成对应目录，例如 `/srv/knowledge-cabin/run_knowledge_cabin.sh --force-run`。
