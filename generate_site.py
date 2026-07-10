#!/usr/bin/env python3
"""
K M Manohar Insights — static site generator.

Reads all posts from the Blogger Atom feed (live URL in production, local
feed.atom fallback for testing), cleans and categorizes each one, and
renders the full self-hosted site (homepage, 5 cluster/category pages,
archive/search, and one full article page per post) into OUTPUT_DIR.

Usage:
    python3 generate_site.py                 # uses FEED_SOURCE env var or live feed
    FEED_SOURCE=feed.atom python3 generate_site.py   # force local file (offline/dev)
"""
import os
import re
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from lib.parser import load_articles
from lib.categorize import get_cluster, cluster_list
from lib.site_cleaner import deep_clean, dedupe_hero_image

SITE_URL = "https://kmmanoharinsights.netlify.app"
SITE_NAME = "K M Manohar Insights"
BLOGSPOT_URL = "https://kmmanohar1602.blogspot.com/"

# Live Blogger Atom feed (paginates automatically via lib.parser's rel="next"
# handling). Overridable via FEED_SOURCE env var for local/offline testing
# against the committed feed.atom snapshot.
LIVE_FEED_URL = "https://kmmanohar1602.blogspot.com/feeds/posts/default?alt=atom&max-results=150"
FEED_SOURCE = os.environ.get("FEED_SOURCE", LIVE_FEED_URL)

OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", "dist"))
STATIC_FILES = ["styles.css", "app.js"]  # copied as-is into OUTPUT_DIR root


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def esc(s):
    return (str(s or "")
            .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def fmt_date(iso_string):
    if not iso_string:
        return ""
    try:
        dt = datetime.fromisoformat(iso_string)
        return dt.strftime("%B %-d, %Y") if os.name != "nt" else dt.strftime("%B %d, %Y")
    except ValueError:
        return iso_string[:10]


def slugify(text):
    text = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return re.sub(r"-{2,}", "-", text)


def build_toc_and_ids(html_content):
    """Scan cleaned article HTML for h2 tags, inject id= anchors, and return
    (modified_html, toc_items). Only h2s get TOC entries — h3/h4 stay as
    in-flow subheads."""
    toc_items = []
    counter = {"n": 0}

    def add_id(match):
        counter["n"] += 1
        heading_text = re.sub(r"<[^>]+>", "", match.group(2)).strip()
        anchor = f"s{counter['n']}"
        toc_items.append((anchor, heading_text))
        return f'<h2 id="{anchor}"{match.group(1)}>{match.group(2)}</h2>'

    modified = re.sub(r"<h2([^>]*)>(.*?)</h2>", add_id, html_content, flags=re.S)
    return modified, toc_items


BACK_TO_TOC = '<p class="back-to-toc"><a href="#article-top">&uarr; Back to Table of Contents</a></p>'


def insert_back_to_toc(html_content, min_sections=2):
    """Insert a 'Back to Table of Contents' link right before each h2 (after
    the first) and at the very end of the content, so every section can
    jump back to the TOC. Skipped entirely for short articles with fewer
    than min_sections headings, where a TOC/back-link adds clutter rather
    than navigation value."""
    positions = [m.start() for m in re.finditer(r"<h2[ >]", html_content)]
    if len(positions) < min_sections:
        return html_content

    # insert before every h2 except the first one, working backwards so
    # earlier insertions don't shift later positions
    for pos in reversed(positions[1:]):
        html_content = html_content[:pos] + BACK_TO_TOC + html_content[pos:]

    return html_content + BACK_TO_TOC


def strip_leading_duplicate_title(html_content, title):
    """Blogger content sometimes repeats the post title as its own h2/h3/h4
    at the very top; drop it since the page <h1> already shows it."""
    pattern = rf"^\s*<h[2-4][^>]*>\s*{re.escape(title.strip())}\s*</h[2-4]>\s*"
    return re.sub(pattern, "", html_content, count=1, flags=re.I)


# --------------------------------------------------------------------------
# Load + prepare all articles
# --------------------------------------------------------------------------

def load_and_prepare():
    print(f"Loading feed from: {FEED_SOURCE}")
    raw_articles = load_articles(FEED_SOURCE)
    print(f"Loaded {len(raw_articles)} articles")

    # Sort oldest -> newest for stable numbering as new posts are appended
    raw_articles.sort(key=lambda a: a["published"])

    articles = []
    for i, a in enumerate(raw_articles, start=1):
        cluster_slug, cluster_name = get_cluster(a["labels"], a["title"], a["content_text"])

        content, toc_items = build_toc_and_ids(
            strip_leading_duplicate_title(
                dedupe_hero_image(deep_clean(a["content"]), a["hero_image"]),
                a["title"],
            )
        )
        content = insert_back_to_toc(content)

        articles.append({
            **a,
            "number": i,
            "cluster_slug": cluster_slug,
            "cluster_name": cluster_name,
            "content_rendered": content,
            "toc_items": toc_items,
            "date_display": fmt_date(a["published"]),
        })

    return articles


# --------------------------------------------------------------------------
# Shared layout pieces
# --------------------------------------------------------------------------

def render_head(title, description, canonical_path, og_image=None, extra_schema=""):
    og_image = og_image or f"{SITE_URL}/assets/og-default.jpg"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="description" content="{esc(description)}">
<link rel="canonical" href="{SITE_URL}{canonical_path}">
<title>{esc(title)} | {SITE_NAME}</title>
<meta property="og:type" content="website">
<meta property="og:site_name" content="{SITE_NAME}">
<meta property="og:title" content="{esc(title)} | {SITE_NAME}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:url" content="{SITE_URL}{canonical_path}">
<meta property="og:image" content="{og_image}">
<meta name="twitter:card" content="summary_large_image">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@400;500;600;700&family=Newsreader:opsz,wght@6..72,500;6..72,600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/styles.css">
<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-8508625480348460" crossorigin="anonymous"></script>
{extra_schema}
</head>
"""


def render_header():
    clusters = cluster_list()
    return """<header class="site-header">
<a class="brand" href="/" aria-label="K M Manohar Insights home"><span class="brand-orbit">KM</span><span>K M Manohar <b>Insights</b></span></a>
<button class="menu-button" type="button" aria-expanded="false" aria-controls="main-nav"><span></span><span></span><i>Menu</i></button>
<nav class="main-nav" id="main-nav" aria-label="Main navigation">
<a href="/#stories">Latest</a><a href="/#topics">Categories</a><a href="/archive/">Archive</a><a href="/search/">Search</a><a href="/#about">About</a><a class="nav-cta" href="/#newsletter">Get insights</a>
</nav>
</header>
"""


def render_footer():
    return f"""<footer><a class="brand" href="/"><span class="brand-orbit">KM</span><span>K M Manohar <b>Insights</b></span></a><p>Where ideas meet impact.</p><div><a href="/#stories">Latest</a><a href="/archive/">Archive</a><a href="/search/">Search</a><a href="/about/">About</a><a href="/contact/">Contact</a><a href="/privacy-policy/">Privacy</a><a href="/terms-and-conditions/">Terms</a><a href="/disclaimer/">Disclaimer</a><a href="{BLOGSPOT_URL}">Blogspot</a></div><small>&copy; <span id="year">2026</span> {SITE_NAME}</small></footer>
<script src="/app.js"></script>
</body>
</html>"""


# --------------------------------------------------------------------------
# Article page
# --------------------------------------------------------------------------

def render_article_page(article, all_articles, index_by_id):
    cluster_slug, cluster_name = article["cluster_slug"], article["cluster_name"]
    total = len(all_articles)
    idx = index_by_id[article["id"]]
    prev_a = all_articles[idx - 1] if idx > 0 else None
    next_a = all_articles[idx + 1] if idx < total - 1 else None

    # up to 6 related articles from the same cluster, most recent first, excluding self
    related = [a for a in reversed(all_articles) if a["cluster_slug"] == cluster_slug and a["id"] != article["id"]][:6]

    toc_html = ""
    if len(article["toc_items"]) >= 2:
        items = "\n".join(f'<li><a href="#{anchor}">{esc(text)}</a></li>' for anchor, text in article["toc_items"])
        toc_html = f'<nav class="toc" id="article-top" aria-label="Table of contents"><h2>In This Article</h2><ol>{items}</ol></nav>'

    tags_html = ""
    if article["labels"]:
        tags_html = f'<p class="tags">{" &middot; ".join("#" + esc(l.replace(" ", "")) for l in article["labels"][:10])}</p>'

    hero_image = article["hero_image"] or f"{SITE_URL}/assets/og-default.jpg"

    related_html = ""
    if related:
        cards = "\n".join(
            f'<a href="/articles/{r["slug"]}/"><span>{r["number"]:03d}</span><h3>{esc(r["title"])}</h3><b>{esc(r["cluster_name"])}</b></a>'
            for r in related
        )
        related_html = f"""<section class="related">
<h2>More from <em>{esc(cluster_name)}</em></h2>
<div class="related-grid">{cards}</div>
</section>"""

    prev_next_html = '<nav class="prev-next" aria-label="Article navigation">'
    if prev_a:
        prev_next_html += f'<a class="pn-prev" href="/articles/{prev_a["slug"]}/"><small>&larr; Previous</small><span>{esc(prev_a["title"])}</span></a>'
    if next_a:
        prev_next_html += f'<a class="pn-next" href="/articles/{next_a["slug"]}/"><small>Next &rarr;</small><span>{esc(next_a["title"])}</span></a>'
    prev_next_html += "</nav>"

    schema = f"""<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "Article",
  "headline": {json.dumps(article["title"])},
  "description": {json.dumps(article["summary"])},
  "author": {{"@type": "Person", "name": "K M Manohar", "url": "{BLOGSPOT_URL}"}},
  "publisher": {{"@type": "Organization", "name": "{SITE_NAME}", "logo": {{"@type": "ImageObject", "url": "{SITE_URL}/assets/profile.png"}}}},
  "image": {json.dumps(hero_image)},
  "datePublished": {json.dumps(article["published"])},
  "dateModified": {json.dumps(article["updated"] or article["published"])},
  "url": "{SITE_URL}/articles/{article['slug']}/"
}}
</script>"""

    body = render_head(
        article["title"], article["summary"], f"/articles/{article['slug']}/",
        og_image=hero_image, extra_schema=schema
    )
    body += f'<body class="subpage">\n{render_header()}\n'
    body += f'<main class="article-page" style="--accent:#2fbf9b">\n<article>\n'
    body += f'<nav class="breadcrumb" aria-label="Breadcrumb"><a href="/">Home</a><i>/</i><a href="/category/{cluster_slug}/">{esc(cluster_name)}</a><i>/</i><span>Article {article["number"]}</span></nav>\n'
    body += f"""<header class="article-hero">
<p class="kicker"><span></span> {esc(cluster_name)} &middot; Article {article["number"]}</p>
<h1>{esc(article["title"])}</h1>
<p class="byline">By <strong>K M Manohar</strong> &middot; {esc(article["date_display"])} &middot; {article["reading_time"]} min read</p>
<div class="article-tags"><a href="/category/{cluster_slug}/">{esc(cluster_name)}</a></div>
</header>
"""
    body += f'<figure class="article-media"><img src="{esc(hero_image)}" alt="{esc(article["title"])}" loading="lazy"></figure>\n'
    body += f'<div class="article-body">\n<p class="lead">{esc(article["summary"])}</p>\n'
    body += toc_html + "\n"
    body += article["content_rendered"] + "\n"
    body += tags_html + "\n"
    body += f'<section class="about-author"><h2>About the Author</h2><p><strong>K M Manohar</strong> is an independent Sci-Tech writer and research curator who explains breakthrough discoveries that are shaping the future of technology.</p></section>\n'
    body += "</div>\n"  # .article-body
    body += related_html + "\n"
    body += prev_next_html + "\n"
    body += "</article>\n</main>\n"
    body += render_footer()
    return body


# --------------------------------------------------------------------------
# Category page
# --------------------------------------------------------------------------

def render_category_page(cluster_slug, cluster_name, members):
    members_sorted = sorted(members, key=lambda a: a["published"], reverse=True)
    rows = "\n".join(
        f"""<article class="archive-item">
<span>{a["number"]:03d}</span>
<h3><a href="/articles/{a['slug']}/">{esc(a["title"])}</a></h3>
<b>{esc(a["cluster_name"])}<small>{esc(a["date_display"])}</small></b>
<i aria-hidden="true">&#8599;</i>
</article>"""
        for a in members_sorted
    )

    body = render_head(
        cluster_name, f"{cluster_name} — independent science & technology analysis from {SITE_NAME}.",
        f"/category/{cluster_slug}/"
    )
    body += f'<body class="subpage">\n{render_header()}\n'
    body += f'<main class="collection-page" style="--accent:#2fbf9b">\n'
    body += f'<nav class="breadcrumb" aria-label="Breadcrumb"><a href="/">Home</a><i>/</i><span>{esc(cluster_name)}</span></nav>\n'
    body += f"""<header class="collection-hero">
<p class="eyebrow">Category</p>
<h1>{esc(cluster_name)}</h1>
<p class="collection-blurb">Independent analysis of {esc(cluster_name.lower())} developments, curated by K M Manohar.</p>
<p class="collection-count">{len(members_sorted)} articles</p>
</header>
"""
    body += f'<div class="archive-list">{rows}</div>\n'
    body += "</main>\n"
    body += render_footer()
    return body


# --------------------------------------------------------------------------
# Archive / Search page (shared shell; app.js drives the client-side widget)
# --------------------------------------------------------------------------

def render_archive_search_page(kind, articles):
    is_search = kind == "search"
    title = "Search" if is_search else "Archive"
    body = render_head(title, f"{title} the full {SITE_NAME} catalog.", f"/{kind}/")
    body += f'<body class="subpage">\n{render_header()}\n'
    body += f'<main class="collection-page" style="--accent:#2fbf9b">\n'
    body += f'<nav class="breadcrumb" aria-label="Breadcrumb"><a href="/">Home</a><i>/</i><span>{title}</span></nav>\n'
    body += f"""<header class="collection-hero">
<p class="eyebrow">{title}</p>
<h1>{"Find a signal." if is_search else "Every article, in order."}</h1>
<p class="collection-blurb">{len(articles)} articles across five clusters — filter by topic or search by keyword.</p>
</header>
"""
    body += """<div class="archive-tools">
<div class="search-box"><span>Search</span><input id="article-search" type="text" placeholder="Search articles..."></div>
<div class="filters">
<button class="active" data-filter="all">All</button>
<button data-filter="digital-intelligence">Digital</button>
<button data-filter="frontier-technologies">Frontier</button>
<button data-filter="human-future">Human</button>
<button data-filter="sustainable-future">Sustainable</button>
<button data-filter="india-society">India</button>
</div>
</div>
<p class="archive-status" id="archive-status"></p>
<div class="archive-list" id="archive-list"></div>
"""
    # data payload the app.js archive widget expects:
    # [number, title, cluster_slug, cluster_name, inExport(bool), slug]
    data = [
        [a["number"], a["title"], a["cluster_slug"], a["cluster_name"], True, a["slug"]]
        for a in sorted(articles, key=lambda a: a["published"], reverse=True)
    ]
    body += f"<script>const articles = {json.dumps(data)};</script>\n"
    body += "</main>\n"
    body += render_footer()
    return body


STATIC_PAGES = {
    "about": {
        "title": "About Us",
        "content": """
<p class="lead">K M Manohar Insights is an independent science and technology publication, written and curated by one person: K M Manohar.</p>
<p>This site exists for a simple reason — most breakthroughs in AI, quantum computing, biotechnology, materials science, and clean energy are reported either too shallowly (a press-release rewrite) or too technically (a paper only specialists can parse). K M Manohar Insights tries to sit in between: independent analysis that explains why a discovery matters, without dumbing it down.</p>
<h2>What we cover</h2>
<p>Every article falls into one of five clusters: Digital Intelligence (AI, cybersecurity, robotics), Frontier Technologies (quantum computing, semiconductors, materials science), Human Future (biotech, health, fundamental science), Sustainable Future (clean energy, climate, emerging systems), and India &amp; Society (policy, defence, space, enterprise).</p>
<h2>Editorial independence</h2>
<p>K M Manohar Insights is self-funded and editorially independent. Articles are not sponsored, and no company has editorial input into what gets covered or how. Where the site earns revenue — for example through advertising — that revenue has no bearing on editorial coverage.</p>
<h2>Get in touch</h2>
<p>Questions, corrections, or story tips are always welcome — see the <a href="/contact/">Contact</a> page.</p>
""",
    },
    "privacy-policy": {
        "title": "Privacy Policy",
        "content": """
<p class="lead">This Privacy Policy explains what information K M Manohar Insights collects, how it is used, and the choices available to visitors.</p>
<h2>Information we collect</h2>
<p>This site does not require account creation and does not directly collect personal information such as your name or address. If you subscribe to the newsletter, we collect the email address you provide, solely to send you updates from this site. You may unsubscribe at any time.</p>
<h2>Cookies and third-party advertising</h2>
<p>This site uses Google AdSense to display advertising. Google, as a third-party vendor, uses cookies to serve ads based on a visitor's prior visits to this and other websites. Google's use of advertising cookies enables it and its partners to serve ads based on your visit to this site and/or other sites on the Internet.</p>
<p>You may opt out of personalized advertising by visiting <a href="https://adssettings.google.com" target="_blank" rel="noopener">Google's Ads Settings</a>. Alternatively, you can opt out of a third-party vendor's use of cookies for personalized advertising by visiting <a href="https://www.aboutads.info" target="_blank" rel="noopener">www.aboutads.info</a>.</p>
<h2>Analytics</h2>
<p>This site may use analytics services to understand aggregate traffic patterns (e.g. which articles are read most, which countries visitors come from). This data is anonymized and aggregated; it is not used to identify individual visitors.</p>
<h2>Third-party links</h2>
<p>Articles may link to external sources, including the Blogspot journal (kmmanohar1602.blogspot.com) and referenced research. This Privacy Policy does not extend to those external sites — please review their own privacy policies.</p>
<h2>Children's privacy</h2>
<p>This site does not knowingly collect information from children under 13. It is a general-audience science and technology publication not directed at children.</p>
<h2>Changes to this policy</h2>
<p>This Privacy Policy may be updated periodically. Continued use of the site after changes are posted constitutes acceptance of the revised policy.</p>
<h2>Contact</h2>
<p>Questions about this policy can be directed via the <a href="/contact/">Contact</a> page.</p>
""",
    },
    "terms-and-conditions": {
        "title": "Terms and Conditions",
        "content": """
<p class="lead">By accessing K M Manohar Insights, you agree to the following terms.</p>
<h2>Content ownership</h2>
<p>All original articles, analysis, and text on this site are the intellectual property of K M Manohar unless otherwise credited. Content may be shared via the provided links; reproduction of full articles elsewhere requires prior written permission.</p>
<h2>No professional advice</h2>
<p>Content on this site is for informational and educational purposes only. Nothing published here constitutes financial, medical, legal, or investment advice. See the full <a href="/disclaimer/">Disclaimer</a> for details.</p>
<h2>External links</h2>
<p>This site links to third-party sources, research papers, and the author's Blogspot journal for reference and further reading. K M Manohar Insights is not responsible for the content, accuracy, or practices of external sites.</p>
<h2>Advertising</h2>
<p>This site displays advertising served by Google AdSense and possibly other advertising partners. Advertisements are clearly distinguishable from editorial content. K M Manohar Insights does not endorse products or services advertised by third parties.</p>
<h2>Limitation of liability</h2>
<p>While every effort is made to ensure accuracy, K M Manohar Insights makes no warranties about the completeness or reliability of any content and will not be liable for any loss or damage arising from its use.</p>
<h2>Changes to these terms</h2>
<p>These terms may be updated from time to time. Continued use of the site constitutes acceptance of the current terms.</p>
""",
    },
    "disclaimer": {
        "title": "Disclaimer",
        "content": """
<p class="lead">The information provided on K M Manohar Insights is for general informational purposes only.</p>
<h2>Not professional advice</h2>
<p>Articles covering health, biotechnology, finance, or policy topics are journalistic analysis, not professional advice. Always consult a qualified professional (a doctor, financial advisor, or lawyer, as appropriate) before making decisions based on information found here.</p>
<h2>Accuracy of information</h2>
<p>Science and technology move quickly. While articles are researched carefully at the time of writing, subsequent developments may supersede specific claims, figures, or conclusions. Readers are encouraged to verify time-sensitive information independently.</p>
<h2>External sources and links</h2>
<p>Articles may reference or link to third-party research, news sources, or the author's own Blogspot journal. K M Manohar Insights does not control and is not responsible for the content of external sites.</p>
<h2>Opinions</h2>
<p>Analysis and commentary reflect the personal views of the author, K M Manohar, and not those of any organization, employer, or institution.</p>
""",
    },
    "contact": {
        "title": "Contact",
        "content": """
<p class="lead">Questions, corrections, story tips, or partnership enquiries — get in touch.</p>
<h2>Email</h2>
<p>The best way to reach K M Manohar Insights is by email: <a href="mailto:kmmanohar@yahoo.com">kmmanohar@yahoo.com</a></p>
<h2>Journal</h2>
<p>You can also find the full archive of articles on the original journal at <a href="https://kmmanohar1602.blogspot.com/" target="_blank" rel="noopener">kmmanohar1602.blogspot.com</a>.</p>
<h2>Corrections</h2>
<p>If you spot an error in any article, please include the article title and a brief description of the issue — corrections are reviewed and addressed promptly.</p>
""",
    },
}


def render_static_page(slug, title, content_html):
    body = render_head(title, f"{title} — {SITE_NAME}.", f"/{slug}/")
    body += f'<body class="subpage">\n{render_header()}\n'
    body += '<main class="article-page" style="--accent:#2fbf9b">\n<article>\n'
    body += f'<nav class="breadcrumb" aria-label="Breadcrumb"><a href="/">Home</a><i>/</i><span>{esc(title)}</span></nav>\n'
    body += f'<header class="article-hero"><h1>{esc(title)}</h1></header>\n'
    body += f'<div class="article-body">{content_html}</div>\n'
    body += "</article>\n</main>\n"
    body += render_footer()
    return body


# --------------------------------------------------------------------------
# Homepage
# --------------------------------------------------------------------------

def render_home_page(articles):
    latest = sorted(articles, key=lambda a: a["published"], reverse=True)
    lead, *rest_bento = latest[:4]
    clusters = cluster_list()

    body = render_head(
        "The future is already here.",
        "We decode what truly matters across artificial intelligence, quantum technology, advanced materials, aerospace, biotechnology and clean energy.",
        "/"
    )
    body += '<body>\n'
    body += render_header()
    body += f"""<section class="hero">
<div class="stars"></div>
<div class="hero-content">
<p class="kicker"><span></span> Independent Science &amp; Technology Analysis</p>
<h1>The future is<br>already <em>here.</em></h1>
<p class="hero-copy">We decode what truly matters across artificial intelligence, quantum technology, advanced materials, aerospace, biotechnology and clean energy.</p>
<div class="hero-actions">
<a class="primary-button" href="#stories">Explore the Signals<span>&rarr;</span></a>
<p><strong>{len(articles)}</strong> Future-facing articles</p>
</div>
</div>
<div class="earth"><div class="earth-glow"></div><div class="earth-surface"></div><div class="signal signal-one"></div><div class="signal signal-two"></div><div class="signal signal-three"></div></div>
<p class="hero-index">AI / QUANTUM / SPACE / HEALTH / ENERGY / INDIA</p>
</section>
"""
    body += """<section class="analyst-strip" id="about">
<div class="analyst-photo"><img src="/assets/profile.png" alt="K M Manohar"></div>
<div class="analyst-copy">
<p class="eyebrow">The Analyst</p>
<h2>K M Manohar</h2>
<h3>Independent Sci-Tech Writer &amp; Research Curator</h3>
<p>K M Manohar explains breakthrough discoveries that are shaping the future of technology — across AI, quantum computing, biotech, materials science, and beyond.</p>
<a href="https://kmmanohar1602.blogspot.com/">Read the journal</a>
</div>
<div class="principles">
<p><span>01</span>Signal over noise</p>
<p><span>02</span>Depth over speed</p>
<p><span>03</span>Independent analysis</p>
</div>
</section>
"""
    lead_card = f"""<a class="bento bento-lead" href="/articles/{lead['slug']}/"><img src="{esc(lead['hero_image'] or '')}" alt="{esc(lead['title'])}"><div class="bento-shade"></div><div><small>{esc(lead['cluster_name'])} &middot; Article {lead['number']}</small><h3>{esc(lead['title'])}</h3><p>{esc(lead['summary'][:110])}</p><b>Read insight &rarr;</b></div></a>"""
    other_cards = "\n".join(
        f"""<a class="bento{' bento-quantum' if i == 0 else ''}" href="/articles/{a['slug']}/"><img src="{esc(a['hero_image'] or '')}" alt="{esc(a['title'])}"><div class="bento-shade"></div><div><small>{esc(a['cluster_name'])} &middot; Article {a['number']}</small><h3>{esc(a['title'])}</h3><b>Read insight &rarr;</b></div></a>"""
        for i, a in enumerate(rest_bento)
    )
    body += f"""<section class="section stories" id="stories">
<div class="section-heading"><h2>Latest <em>Signals</em></h2><p>The newest analysis, updated as breakthroughs happen.</p></div>
<div class="bento-grid">{lead_card}{other_cards}</div>
</section>
"""
    topic_rows = "\n".join(
        f'<a href="/category/{slug}/"><span>{str(i+1).zfill(2)}</span><h3>{esc(name)}</h3><p>{sum(1 for a in articles if a["cluster_slug"] == slug)} articles</p><i>&rarr;</i></a>'
        for i, (slug, name) in enumerate(clusters)
    )
    body += f"""<section class="section topics" id="topics">
<div class="topic-intro"><h2>Five <em>clusters.</em></h2><p>Every article is organized into one of five broad coverage areas.</p></div>
<div class="topic-list">{topic_rows}</div>
</section>
"""
    body += """<section class="section newsletter" id="newsletter">
<h2>Get the<br>signal.</h2>
<form class="signup-form">
<label for="signup-email">Email address</label>
<div><input id="signup-email" type="email" placeholder="you@example.com" required><button type="submit">Subscribe</button></div>
<p>No spam. Unsubscribe anytime.</p>
</form>
</section>
"""
    body += render_footer()
    return body


# --------------------------------------------------------------------------
# Build
# --------------------------------------------------------------------------

def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def build():
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True)

    for f in STATIC_FILES:
        if Path(f).exists():
            shutil.copy(f, OUTPUT_DIR / f)

    if Path("assets").exists():
        shutil.copytree("assets", OUTPUT_DIR / "assets", dirs_exist_ok=True)

    articles = load_and_prepare()
    index_by_id = {a["id"]: i for i, a in enumerate(articles)}

    # Article pages
    for a in articles:
        write(OUTPUT_DIR / "articles" / a["slug"] / "index.html",
              render_article_page(a, articles, index_by_id))

    # Category pages
    for slug, name in cluster_list():
        members = [a for a in articles if a["cluster_slug"] == slug]
        write(OUTPUT_DIR / "category" / slug / "index.html",
              render_category_page(slug, name, members))

    # Archive + Search
    write(OUTPUT_DIR / "archive" / "index.html", render_archive_search_page("archive", articles))
    write(OUTPUT_DIR / "search" / "index.html", render_archive_search_page("search", articles))

    # Static pages (About, Contact, Privacy, Terms, Disclaimer) - required for AdSense
    for slug, page in STATIC_PAGES.items():
        write(OUTPUT_DIR / slug / "index.html",
              render_static_page(slug, page["title"], page["content"]))

    # Homepage
    write(OUTPUT_DIR / "index.html", render_home_page(articles))

    # sitemap.xml
    urls = ["/", "/archive/", "/search/"] + [f"/category/{s}/" for s, _ in cluster_list()] + \
           [f"/{slug}/" for slug in STATIC_PAGES] + \
           [f"/articles/{a['slug']}/" for a in articles]
    sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    sitemap += "\n".join(f"<url><loc>{SITE_URL}{u}</loc></url>" for u in urls)
    sitemap += "\n</urlset>"
    write(OUTPUT_DIR / "sitemap.xml", sitemap)

    # ads.txt - required by Google AdSense for Authorized Digital Sellers verification
    write(OUTPUT_DIR / "ads.txt", "google.com, pub-8508625480348460, DIRECT, f08c47fec0942fa0\n")

    print(f"Built {len(articles)} articles + homepage + 5 category pages + archive + search + {len(STATIC_PAGES)} static pages")
    print(f"Output: {OUTPUT_DIR.resolve()}")


if __name__ == "__main__":
    build()
