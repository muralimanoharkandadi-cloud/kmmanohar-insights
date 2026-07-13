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
        from urllib.request import Request
        req = Request(source, headers={"User-Agent": "Mozilla/5.0 (compatible; KMManoharInsightsBot/1.0)"})
        with urlopen(req, timeout=30) as response:
            return response.read().decode("utf-8")
    else:
        feed = Path(source)

        if not feed.exists():
            raise FileNotFoundError(f"{feed} not found")

        return feed.read_text(
            encoding="utf-8",
            errors="ignore",
        )

def load_entries(source="feed.atom"):
    root = ET.fromstring(load_feed(source))
    return root.findall("atom:entry", ATOM)


def get_next_link(root):
     for link in root.findall("atom:link", ATOM):
        if link.attrib.get("rel") == "next":
            return link.attrib.get("href")
     return None


def load_all_entries(source="feed.atom"):
    if not (source.startswith("http://") or source.startswith("https://")):
        # Local file snapshot - single load, no pagination needed.
        root = ET.fromstring(load_feed(source))
        return root.findall("atom:entry", ATOM)

    # Live feed: paginate explicitly via start-index rather than relying
    # solely on rel="next" links, which can truncate early for some Blogger
    # feed configurations. Dedup by entry id in case of any overlap between
    # pages.
    #
    # Resilience matters here: a single transient empty/failed page
    # mid-sequence must NOT be mistaken for "reached the end of the feed" -
    # that was a real bug (two confirmed-published posts were silently
    # dropped by exactly this). We track Blogger's own reported
    # <openSearch:totalResults> from the first page and keep going,
    # retrying failed requests, until either we've collected that many
    # entries or we've seen several consecutive genuinely-empty pages in
    # a row (the real end-of-feed signal).
    from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
    import time

    OPENSEARCH = {"openSearch": "http://a9.com/-/spec/opensearchrss/1.0/"}

    parts = urlsplit(source)
    params = dict(parse_qsl(parts.query))
    params.pop("start-index", None)
    max_results = int(params.get("max-results", "150"))
    params["max-results"] = str(max_results)

    entries = []
    seen_ids = set()
    start_index = 1
    MAX_PAGES = 60  # safety cap: 60 * max_results comfortably exceeds any realistic post count
    MAX_RETRIES_PER_PAGE = 3
    CONSECUTIVE_EMPTY_LIMIT = 3  # only treat this many empty pages IN A ROW as real end-of-feed

    expected_total = None
    consecutive_empty = 0

    for page_num in range(MAX_PAGES):
        params["start-index"] = str(start_index)
        query = urlencode(params)
        page_url = urlunsplit((parts.scheme, parts.netloc, parts.path, query, ""))

        page_entries = []
        for attempt in range(1, MAX_RETRIES_PER_PAGE + 1):
            try:
                print(f"Loading {page_url} (attempt {attempt})")
                xml = load_feed(page_url)
                root = ET.fromstring(xml)
                page_entries = root.findall("atom:entry", ATOM)

                if expected_total is None:
                    total_text = root.findtext("openSearch:totalResults", default=None, namespaces=OPENSEARCH)
                    if total_text and total_text.isdigit():
                        expected_total = int(total_text)
                        print(f"Blogger reports totalResults={expected_total}")
                break  # success, no need to retry
            except Exception as e:
                print(f"  WARNING: attempt {attempt} failed for start-index={start_index}: {e}")
                if attempt < MAX_RETRIES_PER_PAGE:
                    time.sleep(1.5 * attempt)
                else:
                    print(f"  giving up on start-index={start_index} after {MAX_RETRIES_PER_PAGE} attempts")

        if not page_entries:
            consecutive_empty += 1
            print(f"  empty/failed page ({consecutive_empty}/{CONSECUTIVE_EMPTY_LIMIT} consecutive)")
            if expected_total is not None and len(entries) >= expected_total:
                print("Reached Blogger's reported total - stopping.")
                break
            if consecutive_empty >= CONSECUTIVE_EMPTY_LIMIT:
                print("Multiple consecutive empty pages - treating as genuine end of feed.")
                break
            # don't advance start_index on a failed/empty page - retry the
            # SAME position next loop iteration in case it was transient
            continue

        consecutive_empty = 0
        new_on_this_page = 0
        for entry in page_entries:
            entry_id = entry.findtext("atom:id", default=None, namespaces=ATOM)
            entry_title = entry.findtext("atom:title", default="(no title)", namespaces=ATOM)
            if entry_id and entry_id in seen_ids:
                print(f"    SKIPPED (duplicate id): {entry_title}")
                continue
            if entry_id:
                seen_ids.add(entry_id)
            entries.append(entry)
            new_on_this_page += 1

        print(f"  -> {len(page_entries)} entries on this page, {new_on_this_page} new, {len(entries)} total so far")

        if new_on_this_page == 0:
            # Every entry on this page was already seen. Could be genuine
            # end-of-feed overlap, or a stale/cached response for this
            # start-index - treat it the same as an empty page rather than
            # stopping immediately.
            consecutive_empty += 1
            if expected_total is not None and len(entries) >= expected_total:
                print("Reached Blogger's reported total - stopping.")
                break
            if consecutive_empty >= CONSECUTIVE_EMPTY_LIMIT:
                print("Multiple consecutive all-duplicate pages - treating as genuine end of feed.")
                break
            start_index += max_results
            continue

        if expected_total is not None and len(entries) >= expected_total:
            print("Reached Blogger's reported total - stopping.")
            break

        start_index += max_results

    if expected_total is not None and len(entries) < expected_total:
        print(f"WARNING: collected {len(entries)} entries but Blogger reported "
              f"{expected_total} total - {expected_total - len(entries)} may be missing. "
              f"Check the retry/empty-page messages above for where pagination stopped short.")

    print(f"Pagination complete: {len(entries)} unique entries loaded")
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


def load_articles(source="feed.atom"):
    articles = []

    entries = load_all_entries(source)

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