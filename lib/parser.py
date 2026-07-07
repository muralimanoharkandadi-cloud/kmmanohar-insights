from pathlib import Path
import xml.etree.ElementTree as ET
from html import unescape
import re

from lib.content_cleaner import clean_content

ATOM = {"atom": "http://www.w3.org/2005/Atom"}
BLOGGER = {"blogger": "http://schemas.google.com/blogger/2018"}

def load_feed():
    feed = Path("feed.atom")
    if not feed.exists():
        raise FileNotFoundError("feed.atom not found")
    return feed.read_text(encoding="utf-8")

def load_articles():

    articles = []

    for entry in load_entries():

        t = entry.find("blogger:type", BLOGGER)

        if t is None or t.text != "POST":
            continue

        article = build_article(entry)

        # Skip Blogger pages
        if article["slug"].startswith("p-"):
            continue

        # Skip test posts
        if article["slug"] in {
            "next-test",
            "bento-grid-test",
            "blog-post",
        }:
            continue

        articles.append(article)

    articles.sort(
        key=lambda a: a["published"],
        reverse=True
    )

    return articles

def strip_html(html):
    if not html:
        return ""
    html = re.sub(r"<script.*?>.*?</script>", "", html, flags=re.S|re.I)
    html = re.sub(r"<style.*?>.*?</style>", "", html, flags=re.S|re.I)
    text = re.sub(r"<[^>]+>", " ", html)
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()

def calculate_reading_time(text):
    words = len(text.split())
    return max(1, round(words/200)) if words else 0

def get_title(entry):
    n = entry.find("atom:title", ATOM)
    return n.text.strip() if n is not None and n.text else "Untitled"

def get_slug(entry):
    n = entry.find("blogger:filename", BLOGGER)

    if n is None or not n.text:
        return "no-slug"

    slug = Path(n.text).name.strip()

    if slug.lower().endswith(".html"):
        slug = slug[:-5]

    slug = slug.strip()

    # Remove illegal trailing dots/spaces (Windows)
    slug = slug.rstrip(" .")
    slug = re.sub(r'[<>:"/\\|?*]', "-", slug)
    slug = re.sub(r"\s+", "-", slug)
    slug = re.sub(r"-{2,}", "-", slug)

    return slug

def get_content(entry):
    n = entry.find("atom:content", ATOM)

    if n is None or not n.text:
        return ""

    html = n.text

    # Remove legacy Project A intro block
    html = re.sub(
        r'<p class="lead">.*?</a>\s*',
        "",
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )

    html = re.sub(
        r'<dl class="fact-card">.*?</dl>',
        "",
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )

    html = re.sub(
        r'<a class="source-cta".*?</a>',
        "",
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )

    return html

def get_plain_text(entry):
    return strip_html(get_content(entry))

def get_summary(entry, length=220):
    t = get_plain_text(entry)
    return t if len(t) <= length else t[:length].rsplit(" ",1)[0] + "..."

def get_published(entry):
    n = entry.find("atom:published", ATOM)
    return n.text if n is not None else ""

def get_updated(entry):
    n = entry.find("atom:updated", ATOM)
    return n.text if n is not None else ""

def get_created(entry):
    return get_published(entry)

def get_author(entry):
    n = entry.find("atom:author/atom:name", ATOM)
    return n.text.strip() if n is not None and n.text else ""

def get_labels(entry):
    labels=[]
    for c in entry.findall("atom:category", ATOM):
        term=c.attrib.get("term","").strip()
        if term:
            labels.append(term)
    return sorted(set(labels))

def get_hero_image(entry):
    m = re.search(r'<img[^>]+src=["\\\']([^"\\\']+)["\\\']', get_content(entry), flags=re.I)
    return m.group(1) if m else None

def get_word_count(entry):
    return len(get_plain_text(entry).split())

def get_reading_time(entry):
    return calculate_reading_time(get_plain_text(entry))

def build_article(entry):
    slug=get_slug(entry)
    return {
        "id": slug,
        "title": get_title(entry),
        "slug": slug,
        "url": f"{slug}.html",
        "content": clean_content(get_content(entry)),
        "content_html": get_content(entry),
        "content_text": get_plain_text(entry),
        "summary": get_summary(entry),
        "published": get_published(entry),
        "updated": get_updated(entry),
        "created": get_created(entry),
        "author": get_author(entry),
        "labels": get_labels(entry),
        "image": get_hero_image(entry),
        "hero_image": get_hero_image(entry),
        "hero_alt": "",
        "reading_time": get_reading_time(entry),
        "word_count": get_word_count(entry),
        "canonical_url": "",
    }

def load_entries():
    root = ET.fromstring(load_feed())
    return root.findall("atom:entry", ATOM)