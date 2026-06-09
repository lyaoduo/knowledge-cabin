import hashlib
import json
import os
import sys
import random
from datetime import datetime, timedelta
from html import escape
from urllib.parse import unquote, urljoin, urlparse

import feedparser
import requests
from bs4 import BeautifulSoup

from renderer import render_html


FETCHED_AT_FORMAT = "%Y-%m-%d %H:%M"
DEFAULT_OUTPUT_PATH = "/var/www/html/index.html"
OUTPUT_PATH_ENV = "KNOWLEDGE_CABIN_OUTPUT_PATH"
LOCAL_MEDIA_DIR = "media"
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    )
}
IMAGE_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/svg+xml": ".svg",
}

DROP_TAGS = {
    "script",
    "style",
    "noscript",
    "iframe",
    "form",
    "button",
    "input",
    "svg",
    "canvas",
    "aside",
    "nav",
}
ALLOWED_TAGS = {
    "a",
    "article",
    "blockquote",
    "br",
    "code",
    "div",
    "em",
    "figcaption",
    "figure",
    "h2",
    "h3",
    "h4",
    "hr",
    "i",
    "img",
    "li",
    "ol",
    "p",
    "pre",
    "span",
    "strong",
    "table",
    "tbody",
    "td",
    "th",
    "thead",
    "tr",
    "ul",
}
ALLOWED_ATTRS = {
    "a": {"href", "title", "target", "rel"},
    "img": {"src", "alt", "title", "loading", "decoding"},
    "td": {"colspan", "rowspan"},
    "th": {"colspan", "rowspan"},
}


def log(message):
    print(str(message).encode("gbk", errors="replace").decode("gbk"))


def now_stamp():
    return datetime.now().strftime(FETCHED_AT_FORMAT)


def load_config():
    with open("config.json", "r", encoding="utf-8") as f:
        return json.load(f)


def load_store():
    if os.path.exists("data_store.json"):
        with open("data_store.json", "r", encoding="utf-8") as f:
            return json.load(f)
    return {"articles": []}


def save_store(store):
    with open("data_store.json", "w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False, indent=2)


def should_run_now(strategy, source_id, store):
    current_hour = datetime.now().hour
    current_date = datetime.now().strftime("%Y-%m-%d")
    mode = strategy.get("mode")
    
    if mode == "fixed_hour":
        return current_hour == strategy.get("hour")
        
    if mode == "random_range":
        start = strategy["start_hour"]
        end = strategy["end_hour"]
        
        # 1. 如果当前不在配置的范围内，直接拒绝
        if not (start <= current_hour <= end):
            return False
            
        # 2. 检查缓存（data_store.json），看看今天这个任务是不是已经执行过了
        # 我们需要在 store 结构里加一个 "last_run_records" 字典
        if "last_run_records" not in store:
            store["last_run_records"] = {}
            
        if store["last_run_records"].get(source_id) == current_date:
            return False # 今天已经执行过了，直接跳过，防止一小时内重复触发
            
        # 3. 🎯 核心动态概率魔法：
        # 如果到了结束小时（最后一次机会），必须强制命中，确保 100% 不漏空
        if current_hour == end:
            store["last_run_records"][source_id] = current_date # 标记今天已执行
            return True
            
        # 4. 如果在区间内，但还没到最后一个小时，通过纯粹的概率来决定
        # 剩余可用的小时数
        remaining_hours = end - current_hour + 1
        # 每次有 1/剩余小时 的概率命中
        probability = 1.0 / remaining_hours
        
        if random.random() <= probability:
            store["last_run_records"][source_id] = current_date # 标记今天已执行
            return True
            
    return False


def stable_article_id(source_id, link):
    digest = hashlib.sha1(link.split("#", 1)[0].encode("utf-8")).hexdigest()[:14]
    return f"{source_id}_{digest}"


def parse_time(value):
    if not value:
        return None
    text = str(value).strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo:
            parsed = parsed.astimezone().replace(tzinfo=None)
        return parsed
    except ValueError:
        pass

    candidates = (text, text[:16], text[:19], text[:10])
    for candidate in candidates:
        for fmt in (FETCHED_AT_FORMAT, "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(candidate, fmt)
            except ValueError:
                continue
    return None


def article_sort_time(article):
    return parse_time(article.get("published_at")) or parse_time(article.get("fetched_at")) or datetime.min


def get_entry_date(entry):
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed:
        return datetime(*parsed[:6]).strftime(FETCHED_AT_FORMAT)

    raw = entry.get("published") or entry.get("updated") or ""
    parsed_feed_date = feedparser._parse_date(raw) if raw else None
    if parsed_feed_date:
        return datetime(*parsed_feed_date[:6]).strftime(FETCHED_AT_FORMAT)
    return ""


def strip_html_text(value):
    text = BeautifulSoup(value or "", "html.parser").get_text(" ", strip=True)
    return " ".join(text.split())


def truncate_text(text, limit=180):
    text = " ".join((text or "").split())
    if len(text) <= limit:
        return text
    return text[:limit].rstrip()


def is_safe_url(value):
    parsed = urlparse(value)
    return parsed.scheme in {"", "http", "https", "mailto"}


def is_remote_url(value):
    return urlparse(value or "").scheme in {"http", "https"}


def configured_output_path():
    candidate = (os.getenv(OUTPUT_PATH_ENV) or "").strip()
    return candidate or DEFAULT_OUTPUT_PATH


def resolve_output_dir(output_path=DEFAULT_OUTPUT_PATH):
    output_dir = os.path.dirname(output_path) or "."
    if os.path.isdir(output_dir) and os.access(output_dir, os.W_OK):
        return output_dir
    return "."


def local_media_ref(article_id, filename):
    return f"{LOCAL_MEDIA_DIR}/{article_id}/{filename}"


def media_path(output_dir, ref):
    return os.path.join(output_dir, *ref.split("/"))


def unquote_repeated(value):
    text = value or ""
    for _ in range(4):
        decoded = unquote(text)
        if decoded == text:
            break
        text = decoded
    return text


def image_identity(src):
    text = unquote_repeated((src or "").strip())
    if not text:
        return ""

    lower_text = text.lower()
    nested_positions = [
        lower_text.rfind("https://", 1),
        lower_text.rfind("http://", 1),
    ]
    nested_position = max(nested_positions)
    if nested_position > 0:
        return image_identity(text[nested_position:])

    parsed = urlparse(text)
    if parsed.scheme in {"http", "https"}:
        return parsed._replace(query="", fragment="").geturl().lower()
    return text.replace("\\", "/").lower()


def remove_image_node(img):
    parent = img.parent
    img.decompose()
    remove_empty_image_wrappers(parent)


def remove_empty_image_wrappers(start_node):
    changed = False
    node = start_node
    while node and getattr(node, "name", None) in {"a", "figure", "p"}:
        parent = node.parent
        if node.find("img") or node.get_text(strip=True):
            break
        node.decompose()
        changed = True
        node = parent
    return changed


def cleanup_empty_image_wrappers(soup):
    changed = False
    for tag in list(soup.find_all(["a", "figure", "p"])):
        if tag.parent and not tag.find("img") and not tag.get_text(strip=True):
            tag.decompose()
            changed = True
    return changed


def dedupe_content_images(article):
    content_html = article.get("content_html") or ""
    if "<img" not in content_html:
        return False

    soup = BeautifulSoup(content_html, "html.parser")
    thumbnail_key = image_identity(article.get("thumbnail"))
    seen = set()
    changed = False

    for img in list(soup.find_all("img")):
        src = img.get("src", "").strip()
        key = image_identity(src)
        if not key:
            remove_image_node(img)
            changed = True
            continue
        if key in seen or (thumbnail_key and key == thumbnail_key):
            remove_image_node(img)
            changed = True
            continue
        seen.add(key)

    if changed:
        cleanup_empty_image_wrappers(soup)
        article["content_html"] = "".join(str(child) for child in soup.contents).strip()
    return changed


def image_digest(src):
    key = image_identity(src) or src
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


def image_extension(src, response):
    content_type = response.headers.get("Content-Type", "").split(";", 1)[0].lower()
    if content_type in IMAGE_EXTENSIONS:
        return IMAGE_EXTENSIONS[content_type]

    ext = os.path.splitext(urlparse(src).path)[1].lower()
    if ext in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg"}:
        return ".jpg" if ext == ".jpeg" else ext
    return ".jpg"


def existing_local_image(output_dir, article_id, digest):
    article_media_dir = os.path.join(output_dir, LOCAL_MEDIA_DIR, article_id)
    if not os.path.isdir(article_media_dir):
        return ""
    for filename in os.listdir(article_media_dir):
        stem, ext = os.path.splitext(filename)
        if stem == digest and ext:
            return local_media_ref(article_id, filename)
    return ""


def download_image(src, article_id, output_dir):
    if not is_remote_url(src):
        return src

    digest = image_digest(src)
    existing = existing_local_image(output_dir, article_id, digest)
    if existing:
        return existing

    try:
        res = requests.get(src, headers=REQUEST_HEADERS, timeout=25)
        if res.status_code != 200:
            log(f"Skip image download ({res.status_code}): {src}")
            return src
        content_type = res.headers.get("Content-Type", "").split(";", 1)[0].lower()
        if content_type and not content_type.startswith("image/"):
            log(f"Skip non-image response: {src}")
            return src

        ext = image_extension(src, res)
        filename = f"{digest}{ext}"
        ref = local_media_ref(article_id, filename)
        path = media_path(output_dir, ref)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(res.content)
        return ref
    except Exception as e:
        log(f"Error downloading image {src}: {e}")
        return src


def localize_content_images(article, output_dir):
    content_html = article.get("content_html") or ""
    if "<img" not in content_html:
        soup = BeautifulSoup(content_html, "html.parser")
        changed = cleanup_empty_image_wrappers(soup)
        if changed:
            article["content_html"] = "".join(str(child) for child in soup.contents).strip()
        return changed

    soup = BeautifulSoup(content_html, "html.parser")
    changed = False
    image_refs = {}
    for img in soup.find_all("img"):
        src = img.get("src", "").strip()
        local_src = download_image(src, article["id"], output_dir)
        image_refs[image_identity(src)] = local_src
        if local_src != src:
            img["src"] = local_src
            changed = True

    local_refs = {
        img.get("src", "").strip()
        for img in soup.find_all("img")
        if img.get("src", "").strip().startswith(f"{LOCAL_MEDIA_DIR}/")
    }
    local_refs_by_digest = {
        os.path.splitext(os.path.basename(ref))[0]: ref
        for ref in local_refs
    }
    for link in soup.find_all("a"):
        href = link.get("href", "").strip()
        if not href:
            continue
        local_href = image_refs.get(image_identity(href)) or local_refs_by_digest.get(image_digest(href))
        if local_href and local_href != href:
            link["href"] = local_href
            changed = True

    changed = cleanup_empty_image_wrappers(soup) or changed

    if changed:
        article["content_html"] = "".join(str(child) for child in soup.contents).strip()
    return changed


def localize_article_images(article, output_dir):
    changed = dedupe_content_images(article)

    thumbnail = article.get("thumbnail", "").strip()
    if thumbnail:
        local_thumbnail = download_image(thumbnail, article["id"], output_dir)
        if local_thumbnail != article.get("thumbnail_local"):
            article["thumbnail_local"] = local_thumbnail
            changed = True

    changed = localize_content_images(article, output_dir) or changed
    changed = dedupe_content_images(article) or changed
    return changed


def cleanup_stale_media(output_dir, articles):
    media_root = os.path.join(output_dir, LOCAL_MEDIA_DIR)
    if not os.path.isdir(media_root):
        return

    active_ids = {article["id"] for article in articles}
    for entry in os.listdir(media_root):
        path = os.path.join(media_root, entry)
        if not os.path.isdir(path) or entry in active_ids:
            continue
        for root, _, files in os.walk(path, topdown=False):
            for filename in files:
                os.remove(os.path.join(root, filename))
            if root != path:
                os.rmdir(root)
        os.rmdir(path)


def sanitize_html_fragment(raw_html, base_url=""):
    soup = BeautifulSoup(raw_html or "", "html.parser")

    for tag in list(soup.find_all(True)):
        if not tag.parent:
            continue
        if tag.name in DROP_TAGS:
            tag.decompose()
            continue
        if tag.name not in ALLOWED_TAGS:
            tag.unwrap()
            continue

        allowed_attrs = ALLOWED_ATTRS.get(tag.name, set())
        for attr in list(tag.attrs):
            if attr not in allowed_attrs:
                del tag.attrs[attr]

        if tag.name == "a":
            href = tag.get("href", "").strip()
            if href:
                href = urljoin(base_url, href)
                if is_safe_url(href):
                    tag["href"] = href
                    tag["target"] = "_blank"
                    tag["rel"] = "noopener noreferrer"
                else:
                    del tag.attrs["href"]

        if tag.name == "img":
            src = (
                tag.get("src")
                or tag.get("data-src")
                or tag.get("data-original")
                or tag.get("data-lazy-src")
                or ""
            ).strip()
            if src:
                src = urljoin(base_url, src)
            if src and is_safe_url(src):
                tag["src"] = src
                tag["loading"] = "lazy"
                tag["decoding"] = "async"
                tag["alt"] = tag.get("alt", "").strip()
            else:
                tag.decompose()

    cleaned = "".join(str(child) for child in soup.contents).strip()
    return cleaned


def first_image_from_html(raw_html, base_url=""):
    soup = BeautifulSoup(raw_html or "", "html.parser")
    img = soup.find("img")
    if not img:
        return ""
    src = (
        img.get("src")
        or img.get("data-src")
        or img.get("data-original")
        or img.get("data-lazy-src")
        or ""
    ).strip()
    return urljoin(base_url, src) if src else ""


def extract_meta_thumbnail(soup, base_url):
    selectors = [
        'meta[property="og:image"]',
        'meta[name="twitter:image"]',
        'meta[property="twitter:image"]',
    ]
    for selector in selectors:
        tag = soup.select_one(selector)
        content = tag.get("content", "").strip() if tag else ""
        if content:
            return urljoin(base_url, content)
    return ""


def extract_feed_thumbnail(entry, raw_content="", link=""):
    for collection_name in ("media_thumbnail", "media_content"):
        for media in entry.get(collection_name, []) or []:
            url = media.get("url", "").strip()
            if url:
                return urljoin(link, url)

    for enclosure in entry.get("enclosures", []) or []:
        url = enclosure.get("href", "").strip()
        media_type = enclosure.get("type", "")
        if url and media_type.startswith("image/"):
            return urljoin(link, url)

    for link_item in entry.get("links", []) or []:
        media_type = link_item.get("type", "")
        href = link_item.get("href", "").strip()
        if href and media_type.startswith("image/"):
            return urljoin(link, href)

    return first_image_from_html(raw_content, link)


def content_from_entry(entry):
    content_blocks = entry.get("content", []) or []
    for block in content_blocks:
        value = block.get("value", "")
        if value:
            return value
    return entry.get("summary") or entry.get("description") or ""


def build_article(source_config, title, link, excerpt="", thumbnail="", published_at="", raw_content=""):
    content_html = sanitize_html_fragment(raw_content, link) if raw_content else ""
    content_text = strip_html_text(content_html)
    if not excerpt:
        excerpt = truncate_text(content_text)

    return {
        "id": stable_article_id(source_config["id"], link),
        "category_id": source_config["id"],
        "category_name": source_config["name"],
        "title": title,
        "link": link,
        "excerpt": truncate_text(excerpt),
        "thumbnail": thumbnail,
        "published_at": published_at,
        "fetched_at": now_stamp(),
        "content_html": content_html,
        "content_status": "feed" if content_html else "pending",
        "content_updated_at": "",
    }


def parse_devto(source_config):
    articles = []
    try:
        res = requests.get(source_config["url"], headers=REQUEST_HEADERS, timeout=15)
        if res.status_code != 200:
            return articles
        soup = BeautifulSoup(res.text, "html.parser")

        cards = soup.select(".crayons-story")[: source_config["max_items"]]
        for card in cards:
            title_el = card.select_one(".crayons-story__title a")
            if not title_el:
                continue
            title = title_el.text.strip()
            link = urljoin("https://dev.to", title_el.get("href", ""))
            snippet_el = card.select_one(".styled-formatting")
            excerpt = strip_html_text(snippet_el.text if snippet_el else "")
            articles.append(build_article(source_config, title, link, excerpt))
    except Exception as e:
        log(f"Error crawling {source_config['name']}: {e}")
    return articles


def parse_techcrunch(source_config):
    articles = []
    try:
        res = requests.get(source_config["url"], headers=REQUEST_HEADERS, timeout=15)
        if res.status_code != 200:
            return articles
        soup = BeautifulSoup(res.text, "html.parser")

        posts = soup.select("div.wp-block-post")[: source_config["max_items"]]
        for post in posts:
            title_el = post.select_one("h2.wp-block-post-title a")
            if not title_el:
                continue
            title = title_el.text.strip()
            link = title_el.get("href", "")
            excerpt_el = post.select_one("div.wp-block-post-excerpt")
            excerpt = strip_html_text(excerpt_el.text if excerpt_el else "")
            thumbnail_el = post.select_one("img")
            thumbnail = ""
            if thumbnail_el:
                thumbnail = urljoin(link, thumbnail_el.get("src") or thumbnail_el.get("data-src") or "")
            articles.append(build_article(source_config, title, link, excerpt, thumbnail))
    except Exception as e:
        log(f"Error crawling {source_config['name']}: {e}")
    return articles


def parse_universal_rss(source_config):
    articles = []
    try:
        feed = feedparser.parse(source_config["url"])
        items = feed.entries[: source_config["max_items"]]

        for item in items:
            title = item.get("title", "No Title").strip()
            link = item.get("link", "#")
            raw_content = content_from_entry(item)
            excerpt = strip_html_text(item.get("summary", item.get("description", "")))
            if not excerpt:
                excerpt = strip_html_text(raw_content)
            thumbnail = extract_feed_thumbnail(item, raw_content, link)
            published_at = get_entry_date(item)

            articles.append(
                build_article(
                    source_config=source_config,
                    title=title,
                    link=link,
                    excerpt=excerpt,
                    thumbnail=thumbnail,
                    published_at=published_at,
                    raw_content=raw_content,
                )
            )
    except Exception as e:
        log(f"Error parsing RSS for {source_config['name']}: {e}")
    return articles


def select_content_node(soup, link):
    domain = urlparse(link).netloc.lower()
    selectors = []
    if "dev.to" in domain:
        selectors.extend(
            [
                "#article-body",
                ".crayons-article__body",
                "article .crayons-article__body",
            ]
        )
    if "techcrunch.com" in domain:
        selectors.extend(
            [
                ".wp-block-post-content",
                ".article-content",
                ".entry-content",
                "article .wp-block-group",
            ]
        )

    selectors.extend(["article", "main article", "main"])
    candidates = []
    seen = set()
    for selector in selectors:
        for node in soup.select(selector):
            marker = id(node)
            if marker not in seen:
                candidates.append(node)
                seen.add(marker)

    if not candidates:
        return None

    best = max(candidates, key=lambda node: len(node.get_text(" ", strip=True)))
    if len(best.get_text(" ", strip=True)) < 120:
        return None
    return best


def fetch_article_details(article):
    link = article.get("link", "")
    if not link or link == "#":
        return {}

    try:
        res = requests.get(link, headers=REQUEST_HEADERS, timeout=20)
        if res.status_code != 200:
            return {}
        soup = BeautifulSoup(res.text, "html.parser")
        thumbnail = extract_meta_thumbnail(soup, link)
        content_node = select_content_node(soup, link)
        if not content_node:
            return {"thumbnail": thumbnail}

        raw_content = "".join(str(child) for child in content_node.contents)
        content_html = sanitize_html_fragment(raw_content, link)
        content_text = strip_html_text(content_html)
        if not thumbnail:
            thumbnail = first_image_from_html(content_html, link)
        return {
            "thumbnail": thumbnail,
            "content_html": content_html,
            "content_text": content_text,
        }
    except Exception as e:
        log(f"Error fetching body for {article.get('title', link)}: {e}")
    return {}


def fallback_content(article):
    excerpt_text = article.get("excerpt") or "No local body was captured for this article yet."
    return f"<p>{escape(excerpt_text)}</p>"


def ensure_article_details(article):
    changed = False
    needs_content = article.get("content_status") != "full"
    needs_thumbnail = not article.get("thumbnail")

    if not needs_content and not needs_thumbnail:
        return False

    details = fetch_article_details(article)
    if details.get("thumbnail") and details["thumbnail"] != article.get("thumbnail"):
        article["thumbnail"] = details["thumbnail"]
        changed = True

    if details.get("content_html"):
        article["content_html"] = details["content_html"]
        article["content_status"] = "full"
        article["content_updated_at"] = now_stamp()
        if details.get("content_text") and not article.get("excerpt"):
            article["excerpt"] = truncate_text(details["content_text"])
        changed = True
    elif not article.get("content_html"):
        article["content_html"] = fallback_content(article)
        article["content_status"] = "fallback"
        changed = True

    return changed


def normalize_article(article):
    changed = False
    link = article.get("link", "")
    category_id = article.get("category_id", "article")
    stable_id = stable_article_id(category_id, link) if link else article.get("id", "")
    if stable_id and article.get("id") != stable_id:
        article["id"] = stable_id
        changed = True

    defaults = {
        "excerpt": "",
        "thumbnail": "",
        "thumbnail_local": "",
        "published_at": "",
        "fetched_at": now_stamp(),
        "content_html": "",
        "content_status": "pending",
        "content_updated_at": "",
    }
    for key, value in defaults.items():
        if key not in article:
            article[key] = value
            changed = True

    if article.get("excerpt"):
        clean_excerpt = truncate_text(strip_html_text(article["excerpt"]))
        if clean_excerpt != article["excerpt"]:
            article["excerpt"] = clean_excerpt
            changed = True

    return changed


def prune_articles(store, retention_days):
    cutoff_time = datetime.now() - timedelta(days=retention_days)
    valid_articles = []

    for article in store["articles"]:
        article_time = article_sort_time(article)
        if article_time >= cutoff_time:
            valid_articles.append(article)

    changed = len(valid_articles) != len(store["articles"])
    store["articles"] = valid_articles
    return changed


def merge_article(existing, incoming):
    changed = False
    for key in ("title", "category_name", "published_at"):
        if incoming.get(key) and incoming[key] != existing.get(key):
            existing[key] = incoming[key]
            changed = True

    for key in ("excerpt", "thumbnail", "content_html"):
        if incoming.get(key) and not existing.get(key):
            existing[key] = incoming[key]
            changed = True

    if incoming.get("content_html") and existing.get("content_status") in {"pending", "fallback"}:
        existing["content_status"] = incoming.get("content_status", "feed")
        changed = True

    return changed


def group_categories(config, articles):
    categories = {s["id"]: {"name": s["name"], "articles": []} for s in config["sources"]}
    for article in articles:
        category = categories.get(article["category_id"])
        if category is not None:
            category["articles"].append(article)
    return categories


def main(force_run=False):
    config = load_config()
    store = load_store()
    store.setdefault("articles", [])

    retention_days = config.get("history_retention_days", 7)
    output_path = configured_output_path()
    output_dir = resolve_output_dir(output_path)
    changed = False

    for article in store["articles"]:
        changed = normalize_article(article) or changed
    changed = prune_articles(store, retention_days) or changed

    existing_by_link = {article["link"]: article for article in store["articles"] if article.get("link")}

    for source in config["sources"]:
        if force_run or should_run_now(source["schedule_strategy"], source["id"], store):
            print(f"[{datetime.now().strftime('%H:%M')}] Running task for: {source['name']}")

            if source["type"] == "devto":
                fetched = parse_devto(source)
            elif source["type"] == "techcrunch":
                fetched = parse_techcrunch(source)
            elif source["type"] == "rss":
                fetched = parse_universal_rss(source)
            else:
                log(f"Unknown source type for {source['name']}, skipping.")
                continue

            for item in fetched:
                existing = existing_by_link.get(item["link"])
                if existing:
                    changed = merge_article(existing, item) or changed
                else:
                    store["articles"].append(item)
                    existing_by_link[item["link"]] = item
                    changed = True
        else:
            print(f"[{datetime.now().strftime('%H:%M')}] Skip {source['name']} (Strategy hour not reached)")

    changed = prune_articles(store, retention_days) or changed
    store["articles"].sort(key=article_sort_time, reverse=True)

    for article in store["articles"]:
        changed = ensure_article_details(article) or changed
        changed = localize_article_images(article, output_dir) or changed

    cleanup_stale_media(output_dir, store["articles"])

    if changed:
        save_store(store)

    categories = group_categories(config, store["articles"])
    render_html(categories, output_path=output_path, retention_days=retention_days)


if __name__ == "__main__":
    # 解析命令行参数，如果包含 --force-run 则强制执行一次抓取和更新，否则按照配置的策略决定是否执行。
    force_run = "--force-run" in sys.argv
    main(force_run=force_run)
