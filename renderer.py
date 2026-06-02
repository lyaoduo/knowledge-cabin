import os

def render_html(categories, output_path="/var/www/html/index.html"):
    # 如果本地测试，自动降级输出到当前目录
    if not os.access(os.path.dirname(output_path), os.W_OK):
        output_path = "index.html"
        
    # 生成分类导航标签与分类内容块
    nav_html = ""
    sections_html = ""
    
    for cat_id, cat_data in categories.items():
        if not cat_data["articles"]:
            continue # 如果当前分类最近一周内没内容，隐藏
            
        nav_html += f'<a href="#{cat_id}">{cat_data["name"]}</a>'
        
        sections_html += f'<div class="category-block" id="{cat_id}">'
        sections_html += f'<h2 class="category-title">📂 {cat_data["name"]}</h2>'
        sections_html += '<div class="posts-grid">'
        
        for art in cat_data["articles"]:
            sections_html += f"""
            <article class="post-card">
                <div class="post-meta">⏰ Logged: {art['fetched_at']}</div>
                <h3 class="post-title" onclick="window.open('{art['link']}', '_blank')">{art['title']}</h3>
                <p class="post-excerpt">{art['excerpt']}...</p>
                <a href="{art['link']}" target="_blank" class="read-more">Learn Original Document →</a>
            </article>
            """
        sections_html += '</div></div>'

    # 全局高仿真 UI 模板
    full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dong's Technical Notebook</title>
    <style>
        :root {{ --primary: #0284c7; --text: #0f172a; --bg: #f8fafc; --card-bg: #ffffff; }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: -apple-system, sans-serif; background: var(--bg); color: var(--text); padding-bottom: 60px; }}
        header {{ background: var(--card-bg); border-bottom: 1px solid #e2e8f0; position: sticky; top: 0; z-index: 100; box-shadow: 0 1px 3px rgba(0,0,0,0.02); }}
        .nav-container {{ max-width: 1200px; margin: 0 auto; display: flex; justify-content: space-between; align-items: center; padding: 15px 20px; }}
        .logo {{ font-weight: 700; font-size: 1.15rem; color: var(--primary); text-decoration: none; }}
        .nav-links a {{ text-decoration: none; color: #475569; margin-left: 18px; font-size: 0.9rem; font-weight: 500; padding: 6px 12px; border-radius: 6px; transition: all 0.2s; }}
        .nav-links a:hover {{ background: #f1f5f9; color: var(--primary); }}
        .wrapper {{ max-width: 1200px; margin: 30px auto; padding: 0 20px; }}
        .category-block {{ margin-bottom: 40px; scroll-margin-top: 80px; }}
        .category-title {{ font-size: 1.3rem; font-weight: 700; margin-bottom: 20px; color: #1e293b; border-bottom: 2px solid #e2e8f0; padding-bottom: 6px; }}
        .posts-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(350px, 1fr)); gap: 20px; }}
        @media (max-width: 640px) {{ .posts-grid {{ grid-template-columns: 1fr; }} }}
        .post-card {{ background: var(--card-bg); border-radius: 10px; border: 1px solid #e2e8f0; padding: 20px; display: flex; flex-direction: column; justify-content: space-between; transition: all 0.2s; }}
        .post-card:hover {{ transform: translateY(-2px); box-shadow: 0 10px 25px rgba(0,0,0,0.04); border-color: #cbd5e1; }}
        .post-meta {{ font-size: 0.8rem; color: #94a3b8; margin-bottom: 8px; }}
        .post-title {{ font-size: 1.1rem; font-weight: 600; line-height: 1.4; color: #0f172a; margin-bottom: 10px; cursor: pointer; }}
        .post-title:hover {{ color: var(--primary); }}
        .post-excerpt {{ color: #475569; font-size: 0.9rem; line-height: 1.5; margin-bottom: 15px; flex-grow: 1; }}
        .read-more {{ color: var(--primary); text-decoration: none; font-size: 0.85rem; font-weight: 500; }}
        footer {{ text-align: center; color: #64748b; font-size: 0.85rem; margin-top: 40px; }}
    </style>
</head>
<body>
    <header>
        <nav class="nav-container">
            <a href="#" class="logo">🚀 Dong's Technical Notebook</a>
            <div class="nav-links">
                {nav_html}
            </div>
        </nav>
    </header>

    <div class="wrapper">
        {sections_html}
        <footer>
            <p>&copy; 2026 Dong's Technical Notebook. Automated static knowledge synchronization system.</p>
        </footer>
    </div>
</body>
</html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(full_html)
    print(f"HTML rendered successfully to: {output_path}")
