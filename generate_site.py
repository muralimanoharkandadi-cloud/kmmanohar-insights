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

SOCIAL_LINKS = [
    ("LinkedIn", "Connect on LinkedIn", "https://www.linkedin.com/in/k-m-manohar-50184250/",
     '<path d="M20.45 20.45h-3.55v-5.57c0-1.33-.02-3.03-1.85-3.03-1.85 0-2.14 1.45-2.14 2.94v5.66H9.36V9h3.41v1.56h.05c.47-.9 1.63-1.85 3.36-1.85 3.6 0 4.27 2.37 4.27 5.45v6.29zM5.34 7.43a2.06 2.06 0 1 1 0-4.12 2.06 2.06 0 0 1 0 4.12zM7.12 20.45H3.56V9h3.56v11.45z"/>'),
    ("Facebook", "Follow on Facebook", "https://www.facebook.com/kmmanoharyahoo.co.uk",
     '<path d="M13.5 21v-7.9h2.65l.4-3.08h-3.05V8.05c0-.89.25-1.5 1.52-1.5h1.63V3.8c-.28-.04-1.25-.12-2.37-.12-2.35 0-3.96 1.43-3.96 4.06v2.27H7.66v3.08h2.66V21h3.18z"/>'),
    ("Instagram", "Follow on Instagram", "https://www.instagram.com/kmmanoharyahoo.co.uk/",
     '<path d="M12 8.4a3.6 3.6 0 1 0 0 7.2 3.6 3.6 0 0 0 0-7.2zm0 5.94a2.34 2.34 0 1 1 0-4.68 2.34 2.34 0 0 1 0 4.68zm4.59-6.09a.84.84 0 1 1-1.68 0 .84.84 0 0 1 1.68 0zM20 7.35c-.05-1.1-.3-2.07-1.1-2.87-.8-.8-1.77-1.05-2.87-1.1C14.9 3.32 9.1 3.32 8 3.38c-1.1.05-2.06.3-2.87 1.1-.8.8-1.05 1.77-1.1 2.87C3.97 8.5 3.97 15.5 4.03 16.65c.05 1.1.3 2.07 1.1 2.87.81.8 1.77 1.05 2.87 1.1 1.13.06 6.93.06 8.06 0 1.1-.05 2.07-.3 2.87-1.1.8-.8 1.05-1.77 1.1-2.87.06-1.13.06-7.13 0-8.3zm-1.83 9.55a2.63 2.63 0 0 1-1.48 1.48c-1.02.4-3.45.31-4.69.31s-3.67.09-4.69-.31a2.63 2.63 0 0 1-1.48-1.48c-.4-1.02-.31-3.45-.31-4.69s-.09-3.67.31-4.69A2.63 2.63 0 0 1 7.31 5.6c1.02-.4 3.45-.31 4.69-.31s3.67-.09 4.69.31c.7.27 1.22.79 1.48 1.48.4 1.02.31 3.45.31 4.69s.09 3.67-.31 4.69z"/>'),
    ("X", "Follow on X", "https://x.com/KandadiMurali",
     '<path d="M13.6 10.6 20.4 3h-1.6l-5.9 6.6L8.2 3H3l7.1 10.1L3 21h1.6l6.2-7 5 7H21l-7.4-10.4zm-2.2 2.5-.7-1L5 4.2h2.5l4.6 6.5.7 1 6 8.4h-2.5l-4.9-6.9z"/>'),
    ("Reddit", "Follow on Reddit", "https://www.reddit.com/user/upstairs_medicine375/m/k_m_manohar/",
     '<path d="M22 12.3c0-1.2-1-2.2-2.2-2.2-.6 0-1.1.2-1.5.6-1.5-1-3.5-1.6-5.7-1.7l1-4.5 3.2.7c0 .9.7 1.6 1.6 1.6.9 0 1.6-.7 1.6-1.6s-.7-1.6-1.6-1.6c-.6 0-1.2.4-1.4.9L13.3 3c-.2 0-.3 0-.4.2l-1.1 5-.1.1c-2.2.1-4.3.7-5.8 1.7-.4-.4-.9-.6-1.5-.6C3.1 9.4 2 10.4 2 11.6c0 .8.5 1.6 1.2 2-.1.3-.1.6-.1.9 0 3 3.9 5.5 8.8 5.5s8.8-2.5 8.8-5.5c0-.3 0-.6-.1-.9.9-.3 1.4-1.1 1.4-2zM7.5 13.4c0-.8.7-1.5 1.5-1.5s1.5.7 1.5 1.5S9.8 15 9 15s-1.5-.7-1.5-1.6zm8.2 3.6c-.8.8-2.1 1.2-3.7 1.2s-2.9-.4-3.7-1.2c-.2-.1-.2-.4 0-.5.1-.2.4-.2.5 0 .6.6 1.7 1 3.2 1s2.6-.4 3.2-1c.1-.2.4-.2.5 0 .2.1.2.4 0 .5zm-.2-2.1c-.8 0-1.5-.7-1.5-1.5s.7-1.5 1.5-1.5 1.5.7 1.5 1.5-.7 1.5-1.5 1.5z"/>'),
]

# GISCUS_REPO_ID and GISCUS_CATEGORY_ID must be filled in once Giscus is set
# up on the repo (see README) - until then the comments section renders a
# friendly placeholder instead of a broken embed.
GISCUS_REPO_ID = "R_kgDOTOsTGQ"
GISCUS_CATEGORY_ID = "DIC_kwDOTOsTGc4DBByv"

# Live Blogger Atom feed (paginates automatically via lib.parser's rel="next"
# handling). Overridable via FEED_SOURCE env var for local/offline testing
# against the committed feed.atom snapshot.
LIVE_FEED_URL = "https://kmmanohar1602.blogspot.com/feeds/posts/default?alt=atom&max-results=10"
FEED_SOURCE = os.environ.get("FEED_SOURCE", LIVE_FEED_URL)

OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", "dist"))
STATIC_FILES = ["styles.css", "app.js", "favicon.ico", "robots.txt"]  # copied as-is into OUTPUT_DIR root


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

MISMATCH_STOPWORDS = set("""
the a an of in on at to for with and or but is are was were be been being
this that these those it its as by from into about over under after before
how what why who which new could may might will can how does can's world
first breakthrough scientists researchers just now discovery could would
major update reveals shows study marking research using
""".split())


def _keywords(text, min_len=4):
    words = re.findall(r"[a-zA-Z][a-zA-Z\-]+", text.lower())
    return set(w for w in words if len(w) >= min_len and w not in MISMATCH_STOPWORDS)


def check_summary_mismatch(title, raw_content):
    """Some drafts ended up with a 'Summary' section describing a
    DIFFERENT article entirely (confirmed real case: a neutrino-detector
    article contained a summary about an unrelated coronavirus vaccine
    trial - almost certainly a copy-paste leftover from a different
    draft). Flags near-zero keyword overlap between the title and an
    isolated Summary section as a likely mismatch, for manual review -
    this is advisory only and never blocks the build."""
    m = re.search(r">Summary</span></h\d>\s*<p>(?:<span[^>]*>)?(.*?)(?:</span>)?</p>", raw_content, re.S)
    if not m:
        return None
    summary_text = re.sub(r"<[^>]+>", " ", m.group(1))
    summary_text = re.sub(r"\s+", " ", summary_text).strip()
    if len(summary_text) < 30:
        return None

    title_kw = _keywords(title)
    summary_kw = _keywords(summary_text)
    if not title_kw:
        return None
    overlap_ratio = len(title_kw & summary_kw) / len(title_kw)
    if overlap_ratio <= 0.1:
        return summary_text[:150]
    return None


def load_and_prepare():
    print(f"Loading feed from: {FEED_SOURCE}")
    raw_articles = load_articles(FEED_SOURCE)
    print(f"Loaded {len(raw_articles)} articles")

    # Detect near-duplicate posts (same title, ignoring case/punctuation/
    # whitespace - e.g. a trailing period being the only difference).
    # These produce identical URL slugs and silently collide, with the
    # later one overwriting the earlier one's output page. Keep the
    # earlier-published post as canonical and drop the later duplicate,
    # rather than letting them collide invisibly.
    def _title_key(title):
        return re.sub(r"[^\w\s]", "", title.lower()).split()

    raw_articles.sort(key=lambda a: a["published"])
    seen_title_keys = {}
    deduped = []
    for a in raw_articles:
        key = tuple(_title_key(a["title"]))
        if key in seen_title_keys:
            original = seen_title_keys[key]
            print(f"WARNING: dropping near-duplicate post (same title as an earlier post):")
            print(f"  KEEPING:  {original['published']} - {original['title']}")
            print(f"  DROPPING: {a['published']} - {a['title']}")
            continue
        seen_title_keys[key] = a
        deduped.append(a)

    if len(deduped) < len(raw_articles):
        print(f"Dropped {len(raw_articles) - len(deduped)} near-duplicate post(s); {len(deduped)} unique articles remain")
    raw_articles = deduped

    articles = []
    mismatch_count = 0
    for i, a in enumerate(raw_articles, start=1):
        cluster_slug, cluster_name = get_cluster(a["labels"], a["title"], a["content_text"])

        mismatch = check_summary_mismatch(a["title"], a["content"])
        if mismatch:
            mismatch_count += 1
            print(f"WARNING: possible mismatched Summary section (near-zero keyword overlap with title):")
            print(f"  ARTICLE: {a['title']}")
            print(f"  SUMMARY: {mismatch}...")
            print(f"  -> manual review recommended: /articles/{a['slug']}/")

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

    if mismatch_count:
        print(f"Found {mismatch_count} article(s) with a possibly mismatched Summary section - see warnings above")

    slug_counts = {}
    for a in articles:
        slug_counts[a["slug"]] = slug_counts.get(a["slug"], 0) + 1
    collisions = {slug: count for slug, count in slug_counts.items() if count > 1}
    if collisions:
        print(f"WARNING: {len(collisions)} slug collision(s) detected - these posts will overwrite")
        print("         each other's output page since they share the same URL:")
        for slug, count in collisions.items():
            titles = [a["title"] for a in articles if a["slug"] == slug]
            print(f"  /{slug}/ ({count}x): {titles}")

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
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="alternate" type="application/rss+xml" title="{esc(SITE_NAME)}" href="{SITE_URL}/feed.xml">
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
    return """<a class="skip-link" href="#main-content">Skip to content</a>
<header class="site-header">
<a class="brand" href="/" aria-label="K M Manohar Insights home"><span class="brand-orbit">KM</span><span>K M Manohar <b>Insights</b></span></a>
<button class="menu-button" type="button" aria-expanded="false" aria-controls="main-nav"><span></span><span></span><i>Menu</i></button>
<nav class="main-nav" id="main-nav" aria-label="Main navigation">
<a href="/#stories">Latest</a><a href="/#topics">Categories</a><a href="/archive/">Archive</a><a href="/search/">Search</a><a href="/#about">About</a><a class="nav-cta" href="/#newsletter">Get insights</a>
</nav>
</header>
"""


def render_footer():
    return f"""<footer><a class="brand" href="/"><span class="brand-orbit">KM</span><span>K M Manohar <b>Insights</b></span></a><p>Where ideas meet impact.</p><div><a href="/#stories">Latest</a><a href="/archive/">Archive</a><a href="/search/">Search</a><a href="/feed.xml">RSS</a><a href="/about/">About</a><a href="/contact/">Contact</a><a href="/privacy-policy/">Privacy</a><a href="/terms-and-conditions/">Terms</a><a href="/disclaimer/">Disclaimer</a><a href="{BLOGSPOT_URL}">Blogspot</a></div><small>&copy; <span id="year">2026</span> {SITE_NAME}</small></footer>
<script src="/app.js"></script>
</body>
</html>"""


# --------------------------------------------------------------------------
# Article page
# --------------------------------------------------------------------------

ICON_HEART = '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2"><path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.6l-1-1a5.5 5.5 0 0 0-7.8 7.8l1 1L12 21.2l7.8-7.8 1-1a5.5 5.5 0 0 0 0-7.8z"/></svg>'
ICON_COMMENT = '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 11.5a8.4 8.4 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.4 8.4 0 0 1-3.8-.9L3 21l1.9-5.7a8.4 8.4 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.4 8.4 0 0 1 3.8-.9h.5a8.5 8.5 0 0 1 8 8v.5z"/></svg>'
ICON_FOLLOW = '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.7 21a2 2 0 0 1-3.4 0"/></svg>'
ICON_SHARE = '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><path d="M8.6 13.5l6.8 4M15.4 6.5l-6.8 4"/></svg>'


def render_engagement_bar(article):
    social_html = "".join(
        f'<a href="{url}" target="_blank" rel="noopener" class="social-icon" data-tooltip="{tooltip}" aria-label="{tooltip}">'
        f'<svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor">{svg_path}</svg>'
        f'</a>'
        for name, tooltip, url, svg_path in SOCIAL_LINKS
    )
    return f"""<section class="engagement-bar">
<div class="engagement-prompt">
<h2>Enjoyed this article?</h2>
<p>If this article helped you learn something new, support K M Manohar Insights.</p>
</div>
<div class="engagement-actions">
<button class="engage-btn" data-action="like" data-slug="{esc(article['slug'])}">{ICON_HEART}<span>Like</span><span class="engage-count" data-like-count></span></button>
<button class="engage-btn" data-action="comment">{ICON_COMMENT}<span>Comment</span></button>
<button class="engage-btn" data-action="follow">{ICON_FOLLOW}<span>Follow</span></button>
<button class="engage-btn" data-action="share" data-title="{esc(article['title'])}">{ICON_SHARE}<span>Share</span></button>
</div>
<div class="social-links">
<span>Connect on Social Media</span>
{social_html}
</div>
</section>"""


def render_comments_section():
    if GISCUS_REPO_ID and GISCUS_CATEGORY_ID:
        embed = f"""<script src="https://giscus.app/client.js"
data-repo="muralimanoharkandadi-cloud/kmmanohar-insights"
data-repo-id="{GISCUS_REPO_ID}"
data-category="General"
data-category-id="{GISCUS_CATEGORY_ID}"
data-mapping="pathname"
data-strict="0"
data-reactions-enabled="1"
data-emit-metadata="0"
data-input-position="bottom"
data-theme="preferred_color_scheme"
data-lang="en"
crossorigin="anonymous"
async>
</script>"""
    else:
        embed = '<p class="comments-placeholder">Comments are being set up — check back soon.</p>'
    return f'<section id="comments" class="comments-section"><h2>Discussion</h2>{embed}</section>'


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
</script>
<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  "itemListElement": [
    {{"@type": "ListItem", "position": 1, "name": "Home", "item": "{SITE_URL}/"}},
    {{"@type": "ListItem", "position": 2, "name": {json.dumps(cluster_name)}, "item": "{SITE_URL}/category/{cluster_slug}/"}},
    {{"@type": "ListItem", "position": 3, "name": {json.dumps(article["title"])}, "item": "{SITE_URL}/articles/{article['slug']}/"}}
  ]
}}
</script>"""

    body = render_head(
        article["title"], article["summary"], f"/articles/{article['slug']}/",
        og_image=hero_image, extra_schema=schema
    )
    body += f'<body class="subpage">\n{render_header()}\n'
    body += f'<main class="article-page" id="main-content" style="--accent:#2fbf9b">\n<article>\n'
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
    body += render_engagement_bar(article) + "\n"
    body += render_comments_section() + "\n"
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
    body += f'<main class="collection-page" id="main-content" style="--accent:#2fbf9b">\n'
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
    body += f'<main class="collection-page" id="main-content" style="--accent:#2fbf9b">\n'
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
    body += '<main class="article-page" id="main-content" style="--accent:#2fbf9b">\n<article>\n'
    body += f'<nav class="breadcrumb" aria-label="Breadcrumb"><a href="/">Home</a><i>/</i><span>{esc(title)}</span></nav>\n'
    body += f'<header class="article-hero"><h1>{esc(title)}</h1></header>\n'
    body += f'<div class="article-body">{content_html}</div>\n'
    body += "</article>\n</main>\n"
    body += render_footer()
    return body


def rfc822(iso_string):
    """Convert an ISO 8601 date to RFC 822 format, required by the RSS spec."""
    try:
        dt = datetime.fromisoformat(iso_string)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.strftime("%a, %d %b %Y %H:%M:%S %z")
    except (ValueError, TypeError):
        return ""


def render_rss_feed(articles):
    # Most recent 40 articles - a feed reader doesn't need the full archive,
    # and a smaller payload keeps this fast to fetch/parse for subscribers.
    latest = sorted(articles, key=lambda a: a["published"], reverse=True)[:40]

    items = []
    for a in latest:
        description = esc(a["summary"])
        items.append(f"""<item>
<title>{esc(a['title'])}</title>
<link>{SITE_URL}/articles/{a['slug']}/</link>
<guid isPermaLink="true">{SITE_URL}/articles/{a['slug']}/</guid>
<pubDate>{rfc822(a['published'])}</pubDate>
<category>{esc(a['cluster_name'])}</category>
<description>{description}</description>
</item>""")

    build_date = rfc822(datetime.now(timezone.utc).isoformat())
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
<channel>
<title>{SITE_NAME}</title>
<link>{SITE_URL}/</link>
<description>Independent analysis across artificial intelligence, quantum technology, advanced materials, aerospace, biotechnology and clean energy.</description>
<language>en</language>
<lastBuildDate>{build_date}</lastBuildDate>
<atom:link href="{SITE_URL}/feed.xml" rel="self" type="application/rss+xml"/>
{''.join(items)}
</channel>
</rss>"""


def render_404_page():
    body = render_head("Page Not Found", f"This page doesn't exist on {SITE_NAME}.", "/404.html")
    body += f'<body class="subpage">\n{render_header()}\n'
    body += '<main class="article-page" id="main-content" style="--accent:#2fbf9b">\n<article>\n'
    body += """<header class="article-hero" style="text-align:center">
<p class="kicker" style="justify-content:center"><span></span> 404</p>
<h1>This signal was lost.</h1>
<p class="byline">The page you're looking for doesn't exist, or the link may be outdated.</p>
</header>
<div class="article-body" style="text-align:center">
<p><a class="source-cta" href="/">Back to the homepage</a></p>
</div>
"""
    body += "</article>\n</main>\n"
    body += render_footer()
    return body


# --------------------------------------------------------------------------
# Homepage
# --------------------------------------------------------------------------

def render_home_page(articles):
    latest = sorted(articles, key=lambda a: a["published"], reverse=True)
    lead = latest[0]

    # Fill the remaining 4 slots with the most recent article from each of
    # the other clusters, so the homepage always represents the full
    # breadth of coverage rather than whatever happened to publish most
    # recently (which could all be the same topic in a busy week).
    other_cluster_slugs = [slug for slug, _ in cluster_list() if slug != lead["cluster_slug"]]
    rest_bento = []
    for slug in other_cluster_slugs:
        candidate = next((a for a in latest if a["cluster_slug"] == slug), None)
        if candidate:
            rest_bento.append(candidate)

    clusters = cluster_list()

    body = render_head(
        "The future is already here.",
        "We decode what truly matters across artificial intelligence, quantum technology, advanced materials, aerospace, biotechnology and clean energy.",
        "/"
    )
    body += '<body>\n'
    body += render_header()
    body += '<main id="main-content">\n'
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
<a href="/about/">More about this journal &rarr;</a>
</div>
<div class="principles">
<p><span>01</span>Signal over noise</p>
<p><span>02</span>Depth over speed</p>
<p><span>03</span>Independent analysis</p>
</div>
</section>
"""
    FALLBACK_CARD_IMAGE = "/assets/og-default.jpg"

    def _bento_card(a, extra_class=""):
        img = esc(a["hero_image"] or FALLBACK_CARD_IMAGE)
        summary = esc(a["summary"][:110])
        return (f'<a class="bento{extra_class}" href="/articles/{a["slug"]}/">'
                f'<img src="{img}" alt="{esc(a["title"])}" loading="lazy">'
                f'<div class="bento-shade"></div>'
                f'<div><small>{esc(a["cluster_name"])} &middot; Article {a["number"]}</small>'
                f'<h3>{esc(a["title"])}</h3>'
                f'<p>{summary}</p>'
                f'<b>Read insight &rarr;</b></div></a>')

    lead_card = _bento_card(lead, " bento-lead")
    other_cards = "\n".join(_bento_card(a) for a in rest_bento)
    body += f"""<section class="section stories" id="stories">
<div class="section-heading"><h2>Latest <em>Signals</em></h2><p>The newest analysis from each of our five coverage clusters.</p></div>
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
    body += "</main>\n"
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

    if Path(".well-known").exists():
        shutil.copytree(".well-known", OUTPUT_DIR / ".well-known", dirs_exist_ok=True)

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

    # RSS feed - real content-discovery mechanism for the Follow button
    write(OUTPUT_DIR / "feed.xml", render_rss_feed(articles))

    # Custom 404 page (Netlify auto-detects /404.html at the publish root)
    write(OUTPUT_DIR / "404.html", render_404_page())

    # ads.txt - required by Google AdSense for Authorized Digital Sellers verification
    write(OUTPUT_DIR / "ads.txt", "google.com, pub-8508625480348460, DIRECT, f08c47fec0942fa0\n")

    print(f"Built {len(articles)} articles + homepage + 5 category pages + archive + search + {len(STATIC_PAGES)} static pages")
    print(f"Output: {OUTPUT_DIR.resolve()}")


if __name__ == "__main__":
    build()
