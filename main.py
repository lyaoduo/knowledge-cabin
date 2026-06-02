import json
import os
import random
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup
from renderer import render_html
import feedparser
from datetime import datetime

# 加载配置
def load_config():
    with open('config.json', 'r', encoding='utf-8') as f:
        return json.load(f)

# 加载或初始化本地缓存
def load_store():
    if os.path.exists('data_store.json'):
        with open('data_store.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"articles": []}

def save_store(store):
    with open('data_store.json', 'w', encoding='utf-8') as f:
        json.dump(store, f, ensure_ascii=False, indent=2)

# 判断当前时间是否符合某个目标的抓取策略
def should_run_now(strategy):
    current_hour = datetime.now().hour
    if strategy["mode"] == "fixed_hour":
        return current_hour == strategy["hour"]
    elif strategy["mode"] == "random_range":
        # 在本地/服务器调用时，固定生成一个今天的随机执行小时（基于日期作为种子）
        seed = int(datetime.now().strftime("%Y%m%d")) + strategy["start_hour"]
        random.seed(seed)
        target_hour = random.randint(strategy["start_hour"], strategy["end_hour"])
        return current_hour == target_hour
    return True

# 核心解析器 A: Dev.to
def parse_devto(source_config):
    articles = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        res = requests.get(source_config["url"], headers=headers, timeout=15)
        if res.status_code != 200: return articles
        soup = BeautifulSoup(res.text, 'html.parser')
        
        cards = soup.select('.crayons-story')[:source_config["max_items"]]
        for card in cards:
            title_el = card.select_one('.crayons-story__title a')
            if not title_el: continue
            title = title_el.text.strip()
            link = "https://dev.to" + title_el['href'] if not title_el['href'].startswith('http') else title_el['href']
            
            snippet_el = card.select_one('.styled-formatting')
            excerpt = snippet_el.text.strip()[:180] if snippet_el else "Click to read the latest updates on this topic."
            
            articles.append({
                "id": f"{source_config['id']}_{hash(link)}",
                "category_id": source_config["id"],
                "category_name": source_config["name"],
                "title": title,
                "link": link,
                "excerpt": excerpt,
                "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M")
            })
    except Exception as e:
        print(f"Error crawling {source_config['name']}: {e}")
    return articles

# 核心解析器 B: TechCrunch
def parse_techcrunch(source_config):
    articles = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        res = requests.get(source_config["url"], headers=headers, timeout=15)
        if res.status_code != 200: return articles
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # 匹配 TechCrunch 最新的文章块结构
        posts = soup.select('div.wp-block-post')[:source_config["max_items"]]
        for post in posts:
            title_el = post.select_one('h2.wp-block-post-title a')
            if not title_el: continue
            title = title_el.text.strip()
            link = title_el['href']
            
            excerpt_el = post.select_one('div.wp-block-post-excerpt')
            excerpt = excerpt_el.text.strip()[:180] if excerpt_el else "Latest global venture and technology breakthroughs."
            
            articles.append({
                "id": f"{source_config['id']}_{hash(link)}",
                "category_id": source_config["id"],
                "category_name": source_config["name"],
                "title": title,
                "link": link,
                "excerpt": excerpt,
                "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M")
            })
    except Exception as e:
        print(f"Error crawling {source_config['name']}: {e}")
    return articles

def parse_universal_rss(source_config):
    articles = []
    try:
        # feedparser 会自动伪装 User-Agent 并处理复杂的 XML
        feed = feedparser.parse(source_config["url"])
        
        # 严格限制爬取上限
        items = feed.entries[:source_config["max_items"]]
        
        for item in items:
            title = item.get("title", "No Title").strip()
            link = item.get("link", "#")
            
            # 智能提取摘要：优先拿 summary，没有就拿 description
            excerpt = item.get("summary", item.get("description", "Click to read full documentation."))
            # 清洗掉可能残存的 HTML 标签，只保留 180 字纯文本
            excerpt = BeautifulSoup(excerpt, "html.parser").text.strip()[:180]
            
            articles.append({
                "id": f"{source_config['id']}_{hash(link)}",
                "category_id": source_config["id"],
                "category_name": source_config["name"],
                "title": title,
                "link": link,
                "excerpt": excerpt,
                "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M")
            })
    except Exception as e:
        print(f"Error parsing RSS for {source_config['name']}: {e}")
    return articles


def main(force_run=False):
    config = load_config()
    store = load_store()
    
    # 1. 自动滚动轮替：剔除 7 天以前的旧内容
    retention_days = config.get("history_retention_days", 7)
    cutoff_time = datetime.now() - timedelta(days=retention_days)
    
    valid_articles = []
    for art in store["articles"]:
        art_time = datetime.strptime(art["fetched_at"], "%Y-%m-%d %H:%M")
        if art_time >= cutoff_time:
            valid_articles.append(art)
    store["articles"] = valid_articles

    # 2. 依次检查每个目标源是否满足时间抓取策略
    new_links_fetched = False
    existing_links = {a["link"] for a in store["articles"]}
    
    for source in config["sources"]:
        if force_run or should_run_now(source["schedule_strategy"]):
            print(f"[{datetime.now().strftime('%H:%M')}] Running task for: {source['name']}")
            
            if source["type"] == "devto":
                fetched = parse_devto(source)
            elif source["type"] == "techcrunch":
                fetched = parse_techcrunch(source)
            elif source["type"] == "rss":
                fetched = parse_universal_rss(source)
            else:
                print(f"Unknown source type for {source['name']}, skipping.")
                continue
                
            # 去重合并
            for item in fetched:
                if item["link"] not in existing_links:
                    store["articles"].insert(0, item) # 保证新鲜内容排在最前
                    existing_links.add(item["link"])
                    new_links_fetched = True
        else:
            print(f"[{datetime.now().strftime('%H:%M')}] Skip {source['name']} (Strategy hour not reached)")

    # 3. 只有当产生新内容或者由于过期删除了旧内容时，才触发重新生成 HTML
    if new_links_fetched:
        save_store(store)
    
    # 整理出按类别自动归类的数据供给渲染器
    categories = {s["id"]: {"name": s["name"], "articles": []} for s in config["sources"]}
    for art in store["articles"]:
        if art["category_id"] in categories:
            categories[art["category_id"]]["articles"].append(art)
            
    render_html(categories)

if __name__ == "__main__":
    # 本地直接运行时，默认开启强制抓取（忽略小时策略），方便测试
    main(force_run=True)
