import html
import os
import re
from datetime import datetime


SITE_NAME = "Dong's Field Notes"


def escape_html(value):
    return html.escape(str(value or ""), quote=True)


def safe_article_id(article):
    raw_id = article.get("id") or article.get("title") or "article"
    safe_id = re.sub(r"[^a-zA-Z0-9_-]+", "-", raw_id).strip("-")
    return safe_id[:96] or "article"


def article_filename(article):
    return f"{safe_article_id(article)}.html"


def article_href(article):
    return f"articles/{article_filename(article)}"


def image_src_for_context(src, context):
    src = (src or "").strip().replace("\\", "/")
    if context == "article" and src.startswith("media/"):
        return f"../{src}"
    return src


def article_image_src(article, context):
    src = article.get("thumbnail_local") or article.get("thumbnail") or ""
    return image_src_for_context(src, context)


def content_html_for_article(content_html):
    if not content_html or "media/" not in content_html:
        return content_html

    soup = html_parser(content_html)
    for img in soup.find_all("img"):
        img["src"] = image_src_for_context(img.get("src"), "article")
    for link in soup.find_all("a"):
        href = link.get("href", "")
        if href.replace("\\", "/").startswith("media/"):
            link["href"] = image_src_for_context(href, "article")
    return "".join(str(child) for child in soup.contents).strip()


def output_location(output_path):
    output_dir = os.path.dirname(output_path) or "."
    if os.path.isdir(output_dir) and os.access(output_dir, os.W_OK):
        return output_path, output_dir
    return "index.html", "."


def estimate_read_minutes(content_html):
    text = re.sub(r"<[^>]+>", " ", content_html or "")
    compact = re.sub(r"\s+", "", text)
    return max(1, round(len(compact) / 1200))


def html_parser(value):
    from bs4 import BeautifulSoup

    return BeautifulSoup(value or "", "html.parser")


def thumbnail_html(article, context="index"):
    title = escape_html(article.get("title"))
    category = article.get("category_name") or "KC"
    initials = "".join(part[:1] for part in category.split()[:2]).upper() or "KC"
    fallback = f'<div class="thumb-fallback">{escape_html(initials)}</div>'
    thumbnail = article_image_src(article, context)
    if not thumbnail:
        return fallback
    return (
        f"{fallback}"
        f'<img src="{escape_html(thumbnail)}" alt="{title}" loading="lazy" '
        'decoding="async" onerror="this.remove()">'
    )


def content_status_label(article):
    status = article.get("content_status")
    if status == "full":
        return "Local copy"
    if status == "feed":
        return "RSS copy"
    return "Excerpt copy"


def render_list_item(article):
    title = escape_html(article.get("title"))
    excerpt = escape_html(article.get("excerpt"))
    category = escape_html(article.get("category_name"))
    fetched_at = escape_html(article.get("fetched_at"))
    local_href = article_href(article)

    return f"""
            <article class="post-card">
                <a class="thumb-frame" href="{local_href}" aria-label="{title}">
                    {thumbnail_html(article)}
                </a>
                <div class="post-copy">
                    <div class="post-meta">
                        <span>{category}</span>
                        <span>{fetched_at}</span>
                    </div>
                    <h3 class="post-title"><a href="{local_href}">{title}</a></h3>
                    <p class="post-excerpt">{excerpt}</p>
                </div>
            </article>
"""


def render_article_page(article, css=None):
    css = site_css() if css is None else css
    title = escape_html(article.get("title"))
    category = escape_html(article.get("category_name"))
    fetched_at = escape_html(article.get("fetched_at"))
    published_at = escape_html(article.get("published_at"))
    original_link = escape_html(article.get("link"))
    excerpt = escape_html(article.get("excerpt"))
    content_html = content_html_for_article(article.get("content_html")) or f"<p>{excerpt}</p>"
    read_minutes = estimate_read_minutes(content_html)
    status = escape_html(content_status_label(article))
    time_line = published_at or fetched_at
    hero_media = ""
    hero_src = article_image_src(article, "article")
    if hero_src:
        hero_media = f"""
        <figure class="article-hero-media">
            <img src="{escape_html(hero_src)}" alt="{title}" loading="lazy" decoding="async">
        </figure>
"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} | {SITE_NAME}</title>
    <style>{css}</style>
</head>
<body>
    <header class="site-header">
        <nav class="nav-container">
            <a href="../index.html" class="brand">{SITE_NAME}</a>
        </nav>
    </header>

    <main class="article-shell">
        <a class="back-link" href="../index.html">&larr; Back to notes</a>
        <article class="article-page">
            <div class="article-kicker">
                <span>{category}</span>
                <span>{time_line}</span>
                <span>{read_minutes} min read</span>
                <span>{status}</span>
            </div>
            <h1>{title}</h1>
            {hero_media}
            <div class="article-content">
                {content_html}
            </div>
            <div class="article-footer">
                <a class="source-link" href="{original_link}" target="_blank" rel="noopener noreferrer">Original source</a>
            </div>
        </article>
    </main>
</body>
</html>"""


def iter_index_chunks(categories, retention_days, css):
    nav_html = ""
    total_articles = sum(len(cat["articles"]) for cat in categories.values())
    has_sections = False

    for cat_id, cat_data in categories.items():
        articles = cat_data["articles"]
        if not articles:
            continue

        nav_html += f'<a href="#{escape_html(cat_id)}">{escape_html(cat_data["name"])}</a>'
        has_sections = True

    updated_at = datetime.now().strftime("%Y-%m-%d %H:%M")

    yield f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{SITE_NAME}</title>
    <style>{css}</style>
</head>
<body id="top">
    <header class="site-header">
        <nav class="nav-container">
            <a href="#" class="brand">{SITE_NAME}</a>
            <div class="nav-links">
                {nav_html}
            </div>
        </nav>
    </header>

    <main class="page-shell">
        <section class="overview">
            <div>
                <p class="eyebrow">PERSONAL TECH LOG</p>
                <h1>Notes from the last {retention_days} days</h1>
            </div>
            <dl class="stats">
                <div>
                    <dt>Posts</dt>
                    <dd>{total_articles}</dd>
                </div>
                <div>
                    <dt>Topics</dt>
                    <dd>{sum(1 for cat in categories.values() if cat["articles"])}</dd>
                </div>
                <div>
                    <dt>Updated</dt>
                    <dd>{escape_html(updated_at)}</dd>
                </div>
            </dl>
        </section>
"""

    if not has_sections:
        yield """
        <section class="empty-state">
            <h2>No recent notes</h2>
            <p>This page will update after the next sync.</p>
        </section>
"""
    else:
        for cat_id, cat_data in categories.items():
            articles = cat_data["articles"]
            if not articles:
                continue
            yield f"""
        <section class="category-block" id="{escape_html(cat_id)}">
            <div class="section-heading">
                <div>
                    <p>{escape_html(cat_data["name"])}</p>
                    <h2>{len(articles)} recent notes</h2>
                </div>
                <a href="#top">Back to top</a>
            </div>
            <div class="posts-list">
"""
            for article in articles:
                yield render_list_item(article)
            yield """
            </div>
        </section>
"""

    yield f"""
    </main>

    <footer class="site-footer">
        <p>Generated for {SITE_NAME}. Local article pages stay within the retention window.</p>
    </footer>
</body>
</html>"""


def render_index(categories, retention_days, css=None):
    css = site_css() if css is None else css
    return "".join(iter_index_chunks(categories, retention_days, css))


def site_css():
    return """
        :root {
            --bg: #f6f7fb;
            --surface: #ffffff;
            --surface-soft: #eef6f4;
            --text: #151922;
            --muted: #667085;
            --line: #d9dee7;
            --accent: #0f766e;
            --accent-strong: #0b5d56;
            --accent-warm: #be123c;
            --shadow: 0 12px 30px rgba(21, 25, 34, 0.08);
        }

        * {
            box-sizing: border-box;
        }

        body {
            margin: 0;
            background: var(--bg);
            color: var(--text);
            font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            line-height: 1.5;
        }

        a {
            color: inherit;
        }

        .site-header {
            position: sticky;
            top: 0;
            z-index: 20;
            border-bottom: 1px solid rgba(217, 222, 231, 0.85);
            background: rgba(255, 255, 255, 0.92);
            backdrop-filter: blur(14px);
        }

        .nav-container {
            width: min(1180px, calc(100% - 32px));
            min-height: 64px;
            margin: 0 auto;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 16px;
        }

        .brand {
            color: var(--text);
            font-size: 1rem;
            font-weight: 800;
            text-decoration: none;
            white-space: nowrap;
        }

        .nav-links {
            display: flex;
            align-items: center;
            justify-content: flex-end;
            gap: 8px;
            flex-wrap: wrap;
        }

        .nav-links a,
        .back-link,
        .section-heading a,
        .source-link {
            border-radius: 8px;
            text-decoration: none;
            font-size: 0.88rem;
            font-weight: 700;
        }

        .nav-links a {
            border: 1px solid var(--line);
            color: #344054;
            padding: 8px 11px;
            background: #fff;
        }

        .nav-links a:hover {
            border-color: var(--accent);
            color: var(--accent);
        }

        .page-shell,
        .article-shell {
            width: min(1180px, calc(100% - 32px));
            margin: 0 auto;
        }

        .overview {
            display: flex;
            align-items: end;
            justify-content: space-between;
            gap: 28px;
            padding: 38px 0 30px;
            border-bottom: 1px solid var(--line);
        }

        .eyebrow,
        .section-heading p {
            margin: 0 0 6px;
            color: var(--accent-warm);
            font-size: 0.74rem;
            font-weight: 800;
            letter-spacing: 0;
            text-transform: uppercase;
        }

        h1 {
            margin: 0;
            max-width: 760px;
            font-size: clamp(2rem, 4vw, 3.6rem);
            line-height: 1.05;
            letter-spacing: 0;
        }

        .stats {
            margin: 0;
            display: grid;
            grid-template-columns: repeat(3, minmax(86px, 1fr));
            gap: 10px;
        }

        .stats div {
            min-width: 0;
            border-left: 3px solid var(--accent);
            padding: 4px 0 4px 12px;
        }

        .stats dt {
            color: var(--muted);
            font-size: 0.78rem;
            font-weight: 700;
        }

        .stats dd {
            margin: 2px 0 0;
            font-size: 1.1rem;
            font-weight: 800;
            white-space: nowrap;
        }

        .category-block {
            padding: 30px 0 10px;
            scroll-margin-top: 86px;
        }

        .section-heading {
            display: flex;
            align-items: end;
            justify-content: space-between;
            gap: 18px;
            margin-bottom: 16px;
        }

        .section-heading h2 {
            margin: 0;
            font-size: 1.35rem;
            line-height: 1.25;
        }

        .section-heading a,
        .back-link,
        .source-link {
            color: var(--muted);
        }

        .section-heading a:hover,
        .back-link:hover,
        .source-link:hover {
            color: var(--accent);
        }

        .posts-list {
            display: flex;
            flex-direction: column;
            gap: 18px;
        }

        .post-card {
            display: grid;
            grid-template-columns: 220px minmax(0, 1fr);
            gap: 20px;
            align-items: stretch;
            min-width: 0;
            overflow: hidden;
            border: 1px solid rgba(217, 222, 231, 0.9);
            border-radius: 10px;
            background: var(--surface);
            box-shadow: 0 10px 26px rgba(21, 25, 34, 0.07);
            transition: border-color 0.18s ease, box-shadow 0.18s ease, transform 0.18s ease;
        }

        .post-card:hover {
            border-color: rgba(15, 118, 110, 0.38);
            box-shadow: 0 16px 36px rgba(21, 25, 34, 0.11);
            transform: translateY(-1px);
        }

        .thumb-frame {
            position: relative;
            display: block;
            overflow: hidden;
            width: 220px;
            min-height: 160px;
            background: var(--surface-soft);
            text-decoration: none;
        }

        .thumb-frame img {
            position: absolute;
            inset: 0;
            width: 100%;
            height: 100%;
            object-fit: cover;
        }

        .thumb-fallback {
            position: absolute;
            inset: 0;
            display: grid;
            place-items: center;
            color: var(--accent-strong);
            background: linear-gradient(135deg, #dff3ef, #f6e7ee);
            font-size: 1.35rem;
            font-weight: 900;
        }

        .post-copy {
            min-width: 0;
            display: flex;
            flex: 1;
            flex-direction: column;
            justify-content: center;
            padding: 20px 22px 20px 0;
        }

        .post-meta,
        .article-kicker {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            color: var(--muted);
            font-size: 0.76rem;
            font-weight: 700;
        }

        .post-title {
            margin: 9px 0 8px;
            font-size: 1.35rem;
            line-height: 1.32;
        }

        .post-title a {
            text-decoration: none;
        }

        .post-title a:hover {
            color: var(--accent);
        }

        .post-excerpt {
            margin: 0;
            color: #475467;
            display: -webkit-box;
            overflow: hidden;
            -webkit-box-orient: vertical;
            -webkit-line-clamp: 3;
        }

        .site-footer {
            width: min(1180px, calc(100% - 32px));
            margin: 24px auto 48px;
            color: var(--muted);
            font-size: 0.86rem;
        }

        .empty-state {
            padding: 72px 0;
            color: var(--muted);
        }

        .empty-state h2 {
            margin: 0 0 8px;
            color: var(--text);
        }

        .article-shell {
            padding: 28px 0 64px;
        }

        .back-link {
            display: inline-flex;
            margin-bottom: 24px;
        }

        .article-page {
            max-width: 820px;
        }

        .article-page h1 {
            margin: 14px 0 20px;
            font-size: clamp(2rem, 4vw, 3.2rem);
        }

        .article-hero-media {
            margin: 0 0 26px;
            overflow: hidden;
            border-radius: 8px;
            background: var(--surface-soft);
        }

        .article-hero-media img {
            display: block;
            width: 100%;
            aspect-ratio: 16 / 9;
            object-fit: cover;
        }

        .article-content {
            color: #2f3746;
            font-size: 1.04rem;
        }

        .article-content > *:first-child {
            margin-top: 0;
        }

        .article-content p,
        .article-content ul,
        .article-content ol,
        .article-content blockquote,
        .article-content pre,
        .article-content table,
        .article-content figure {
            margin: 0 0 1.1rem;
        }

        .article-content h2,
        .article-content h3,
        .article-content h4 {
            margin: 1.8rem 0 0.7rem;
            color: var(--text);
            line-height: 1.2;
        }

        .article-content a {
            color: var(--accent);
            font-weight: 700;
        }

        .article-content img {
            max-width: 100%;
            height: auto;
            border-radius: 8px;
        }

        .article-content blockquote {
            border-left: 4px solid var(--accent);
            padding-left: 16px;
            color: #475467;
        }

        .article-content pre {
            overflow-x: auto;
            border-radius: 8px;
            background: #171b22;
            color: #f4f7fb;
            padding: 16px;
        }

        .article-content code {
            font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
        }

        .article-content table {
            width: 100%;
            border-collapse: collapse;
            overflow-x: auto;
        }

        .article-content th,
        .article-content td {
            border: 1px solid var(--line);
            padding: 10px;
            text-align: left;
        }

        .article-footer {
            margin-top: 32px;
            padding-top: 20px;
            border-top: 1px solid var(--line);
        }

        .source-link {
            display: inline-flex;
            align-items: center;
            min-height: 36px;
        }

        @media (max-width: 820px) {
            .overview {
                align-items: stretch;
                flex-direction: column;
                gap: 20px;
            }

            .stats {
                grid-template-columns: repeat(3, minmax(0, 1fr));
            }

            .post-card {
                grid-template-columns: 148px minmax(0, 1fr);
                align-items: start;
                gap: 16px;
            }

            .thumb-frame {
                width: 148px;
                min-height: 132px;
            }

            .post-copy {
                padding: 16px 16px 16px 0;
            }
        }

        @media (max-width: 560px) {
            .nav-container {
                align-items: flex-start;
                flex-direction: column;
                padding: 12px 0;
            }

            .nav-links {
                justify-content: flex-start;
            }

            .stats {
                grid-template-columns: 1fr;
            }

            .section-heading {
                align-items: flex-start;
                flex-direction: column;
            }

            .post-card {
                grid-template-columns: 104px minmax(0, 1fr);
                gap: 12px;
            }

            .thumb-frame {
                width: 104px;
                min-height: 112px;
            }

            .post-copy {
                padding: 14px 14px 14px 0;
            }

            .post-title {
                font-size: 1.08rem;
            }
        }
    """


def write_file(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def write_chunks(path, chunks):
    with open(path, "w", encoding="utf-8") as f:
        for chunk in chunks:
            f.write(chunk)


def cleanup_article_pages(articles_dir, active_files):
    if not os.path.isdir(articles_dir):
        return 0

    removed = 0
    for filename in os.listdir(articles_dir):
        path = os.path.join(articles_dir, filename)
        if filename.endswith(".html") and os.path.isfile(path) and filename not in active_files:
            os.remove(path)
            removed += 1
    return removed


def render_html(categories, output_path="/var/www/html/index.html", retention_days=7):
    output_path, output_dir = output_location(output_path)
    articles_dir = os.path.join(output_dir, "articles")
    os.makedirs(articles_dir, exist_ok=True)
    css = site_css()

    active_files = set()
    for category in categories.values():
        for article in category["articles"]:
            filename = article_filename(article)
            active_files.add(filename)
            write_file(os.path.join(articles_dir, filename), render_article_page(article, css))

    removed = cleanup_article_pages(articles_dir, active_files)
    write_chunks(output_path, iter_index_chunks(categories, retention_days, css))
    print(f"HTML rendered successfully to: {output_path}")
    print(f"Article pages rendered: {len(active_files)}; stale pages removed: {removed}")
