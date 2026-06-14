# Knowledge Cabin - 本地测试指南

这是一个高度仿真的全自动、模块化静态知识同步项目。它能将多个远程教学源自动归类，自动实现数据滚动合并，并且只保留最近 7 天内的新鲜内容。

## 🚀 本地快速开始

### 1. 搭建本地环境

确保本地已安装 Python 3.x，安装依赖解析包：

```bash
pip install requests beautifulsoup4 lxml feedparser
```

### 2. 执行首次本地爬取

在当前目录下直接运行主程序：

```bash
python main.py --force-run
```

### 3. 查看本地渲染结果

运行完成后，你会在当前目录下看见这些新生成的内容：

- `data_store.json`：本地的 7 天数据滚动缓冲池。
- `index.html`：带缩略图的分类科技知识看板。
- `articles/`：最近 7 天文章的本地正文页面。
- `media/`：正文页和列表缩略图使用的本地图片缓存。

直接双击 `index.html`，即可在本地电脑浏览器上直接预览最终部署到服务器上的网页效果。

## 🚀 服务器部署指南

参考: [deploy.md](deploy.md)

## 服务器排查注意事项

### 1. 页面没更新时先看发布链路

`Updated` 显示的是 `index.html` 被重新渲染的时间。如果定时任务执行了，但网页上的 `Updated` 仍然停在旧时间，通常说明任务没有成功写入或发布到 Nginx 目录。

先手动强制运行一次：

```bash
~/knowledge-cabin/run_knowledge_cabin.sh --force-run
```

成功时应看到类似：

```text
HTML rendered successfully to: /home/ubuntu/knowledge-cabin/.site/index.html
Article pages rendered: 56; stale pages removed: 0
已通过 sudo 同步静态文件到: /var/www/html
```

再对比 staging 和线上文件：

```bash
grep -n "Updated" ~/knowledge-cabin/.site/index.html /var/www/html/index.html
curl -s http://127.0.0.1/ | grep -A6 "Updated"
```

### 2. 避免用 root 运行主程序

主程序会写 `data_store.json`、`articles/`、`media/` 和 `.site/`。如果曾经用 `sudo python main.py` 或 root 身份运行过，可能导致这些文件属于 root，之后 cron 以 `ubuntu` 用户运行时会报：

```text
PermissionError: [Errno 13] Permission denied: 'data_store.json'
```

修复：

```bash
sudo chown -R ubuntu:ubuntu /home/ubuntu/knowledge-cabin
chmod -R u+rwX /home/ubuntu/knowledge-cabin
```

然后重新执行：

```bash
~/knowledge-cabin/run_knowledge_cabin.sh --force-run
```

### 3. `sudo -i` 不问密码不等于 cron 一定能 sudo

终端里执行 `sudo -i` 不问密码，可能只是 sudo 凭据缓存。脚本使用的是非交互式 sudo：

```bash
sudo -n true
```

检查真实免密 sudo：

```bash
sudo -k
sudo -n true
echo $?
sudo -l
```

如果 `sudo -l` 里有：

```text
(ALL) NOPASSWD: ALL
```

说明当前用户可以免密 sudo，发布到 `/var/www/html` 理论上可行。

### 4. 给 cron 留日志

不要长期把定时任务输出全部丢掉，否则权限错误会被吞掉。推荐把 crontab 改成：

```cron
0 * * * * /home/ubuntu/knowledge-cabin/run_knowledge_cabin.sh >> /home/ubuntu/knowledge-cabin/cron.log 2>&1
```

查看最近错误：

```bash
tail -100 ~/knowledge-cabin/cron.log
```

### 5. `/var/www/html` 下的额外目录可能被删除

部署脚本会把 `.site/` 镜像同步到 `/var/www/html/`：

```bash
sudo -n rsync -a --delete "$SITE_BUILD_DIR/" "$PUBLISH_DIR/"
```

`--delete` 会删除 `/var/www/html/` 中不存在于 `.site/` 的额外文件或目录。不要把其它页面直接放在 `/var/www/html/sub` 这类目录里，除非你修改同步策略。可选方案：

- 把其它页面放到独立 Nginx root，例如 `/srv/www/sub`，用单独域名访问。
- 把本项目发布到 `/var/www/html/blog`，让 `/var/www/html/sub` 不再位于本项目同步根目录。
- 在 `rsync` 中加入排除规则，例如 `--exclude 'sub/'`。
