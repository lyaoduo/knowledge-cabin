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
