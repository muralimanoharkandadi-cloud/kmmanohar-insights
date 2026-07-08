from pathlib import Path
import xml.etree.ElementTree as ET
from html import unescape
import re
from urllib.request import urlopen

from lib.content_cleaner import clean_content

ATOM = {
    "atom": "http://www.w3.org/2005/Atom"
}


def load_feed(source="feed.atom"):
    if source.startswith("http://") or source.startswith("https://"):
        with urlopen(source) as response:
            return response.read().decode("utf-8")
    else:
        feed = Path(source)

        if not feed.exists():
            raise FileNotFoundError(f"{feed} not found")

        return feed.read_text(
            encoding="utf-8",
            errors="ignore",
        )

def load_entries():
    root = ET.fromstring(load_feed())
    return root.findall("atom:entry", ATOM)


def get_next_link(root):
     for link in root.findall("atom:link", ATOM):
        if link.attrib.get("rel") == "next":
            return link.attrib.get("href")
     return None


def load_all_entries():
    xml = load_feed()
    root = ET.fromstring(xml)

    entries = []

    while True:
        entries.extend(root.findall("atom:entry", ATOM))

        next_url = get_next_link(root)

        if not next_url:
            break

        print(f"Loading {next_url}")

        xml = load_feed(next_url)
        root = ET.fromstring(xml)

    return entries


def strip_html(html):
    if not html:
        return ""

    html = re.sub(
        r"<script.*?>.*?</script>",
        "",
        html,
        flags=re.S | re.I,
    )

    html = re.sub(
        r"<style.*?>.*?</style>",
        "",
        html,
        flags=re.S | re.I,
    )

    text = re.sub(r"<[^>]+>", " ", html)
    text = unescape(text)

    return re.sub(r"\s+", " ", text).strip()


def calculate_reading_time(text):
    words = len(text.split())

    if words == 0:
        return 0

    return max(1, round(words / 200))
def get_title(entry):
    node = entry.find("atom:title", ATOM)

    if node is None or not node.text:
        return "Untitled"

    return node.text.strip()


def get_alternate_link(entry):
    for link in entry.findall("atom:link", ATOM):
        if link.attrib.get("rel") == "alternate":
            href = link.attrib.get("href", "").strip()

            # Ignore blog homepage
            if href.endswith(".blogspot.com/"):
                continue

            return href

    return ""


def get_slug(entry):
    href = get_alternate_link(entry)

    if not href:
        return "no-slug"

    slug = Path(href).stem

    slug = slug.rstrip(" .")
    slug = re.sub(r'[<>:"/\\|?*]', "-", slug)
    slug = re.sub(r"\s+", "-", slug)
    slug = re.sub(r"-{2,}", "-", slug)

    return slug


def get_published(entry):
    node = entry.find("atom:published", ATOM)

    if node is None:
        return ""

    return node.text.strip()


def get_updated(entry):
    node = entry.find("atom:updated", ATOM)

    if node is None:
        return ""

    return node.text.strip()


def get_created(entry):
    return get_published(entry)


def get_author(entry):
    node = entry.find("atom:author/atom:name", ATOM)

    if node is None or not node.text:
        return ""

    return node.text.strip()


def get_labels(entry):
    labels = []

    for category in entry.findall("atom:category", ATOM):
        term = category.attrib.get("term", "").strip()

        if term:
            labels.append(term)

    return sorted(set(labels))
def get_content(entry):
    node = entry.find("atom:content", ATOM)

    if node is None or node.text is None:
        return ""

    return node.text


def get_plain_text(entry):
    return strip_html(get_content(entry))


def get_summary(entry, length=220):
    text = get_plain_text(entry)

    if len(text) <= length:
        return text

    return text[:length].rsplit(" ", 1)[0] + "..."


def get_hero_image(entry):
    html = get_content(entry)

    if not html:
        return None

    # First image in article
    match = re.search(
        r'<img[^>]+src=["\']([^"\']+)["\']',
        html,
        flags=re.IGNORECASE,
    )

    if match:
        return match.group(1)

    # Fallback to media:thumbnail if present
    for child in entry:
        if child.tag.endswith("thumbnail"):
            url = child.attrib.get("url") or child.attrib.get("src")

            if url:
                return url

    return None


def get_word_count(entry):
    return len(get_plain_text(entry).split())


def get_reading_time(entry):
    return calculate_reading_time(get_plain_text(entry))
def build_article(entry):
    slug = get_slug(entry)

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


def load_articles():
    articles = []

    entries = load_all_entries()

    print(f"Loaded {len(entries)} entries")

    seen = set()

    for entry in entries:

        slug = get_slug(entry)

        # Skip invalid entries
        if slug == "no-slug":
            continue

        # Skip duplicate posts
        if slug in seen:
            continue

        seen.add(slug)

        # Skip Blogger Pages (/p/)
        href = get_alternate_link(entry)

        if "/p/" in href:
            continue

        # Skip test posts
        if slug in {
            "next-test",
            "bento-grid-test",
            "blog-post",
        }:
            continue

        articles.append(build_article(entry))

    articles.sort(
        key=lambda article: article["published"],
        reverse=True,
    )

    return articles