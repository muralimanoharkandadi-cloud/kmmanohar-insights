"""
Second-pass cleaner, applied after lib.content_cleaner.clean_content().

Handles two realities of this specific content set:

1. Plain (not-yet-recoded) Blogger posts: every paragraph is wrapped in
   <span style="font-family: verdana; ..."> from the original ChatGPT
   drafting workflow, plus Blogger's own <a name="more"> markers and
   <a href="...">-wrapped lightbox images.

2. Posts already recoded into the "Signal Depth Navigator" Blogger bento
   template (a separate, ongoing project): these carry their own
   <a name="sN"> anchors, .bento-* TOC markup, a "Signal Depth Navigator"
   heading, back-btn / explore-btn links pointing at old Blogger-relative
   URLs, a "Visit Us on:" promo line, and a duplicate "About the Author"
   section — all of which this generator already renders itself, so the
   duplicates must be stripped rather than kept.
"""
from bs4 import BeautifulSoup
import re

HASHTAG_LINE_RE = re.compile(r"^(#\S+[\s,&middot;\u00b7]*)+$")


def deep_clean(html: str) -> str:
    if not html:
        return ""

    from bs4 import Comment
    soup = BeautifulSoup(html, "html.parser")

    # Strip HTML comments (design-spec notes some drafts left embedded)
    for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
        comment.extract()

    # Strip any embedded <style>/<script> blocks (e.g. the Signal Depth
    # Navigator's own inline CSS baked into already-recoded posts) — this
    # site's own styles.css already covers everything needed.
    for tag in soup.find_all(["style", "script"]):
        tag.decompose()

    # Strip Microsoft Word export junk (<o:p> spacer tags, Mso* classes)
    # left over from posts originally drafted in Word/ChatGPT and pasted
    # into Blogger without cleanup.
    for tag in soup.find_all("o:p"):
        tag.decompose()
    for tag in soup.find_all(class_=lambda c: c and any(
        cls.lower().startswith("mso") for cls in (c if isinstance(c, list) else [c])
    )):
        del tag["class"]

    # Strip all leftover inline style attributes (font-family, text-align,
    # mso-* properties, etc.) — this site's own styles.css owns typography
    # now, so none of these per-element overrides should survive.
    for tag in soup.find_all(style=True):
        del tag["style"]

    # Unwrap every span (legacy font-family/size styling only, no semantic value)
    for span in soup.find_all("span"):
        span.unwrap()

    # Remove Blogger same-page anchors: <a name="more">, <a name="s3">, <a name="top">
    for a in soup.find_all("a"):
        if a.get("name") and not a.get("href"):
            a.decompose()

    # Unwrap lightbox-style <a href="...blogger...img..."><img></a> so images
    # aren't wrapped in a dead link to Blogger's own image host
    for a in soup.find_all("a", href=True):
        if a.find("img") and len(a.find_all(recursive=False)) == 1 and not a.get_text(strip=True):
            a.unwrap()

    # If this post was already run through the Signal Depth Navigator
    # (Blogger bento) recode, strip its structural leftovers entirely —
    # this generator renders its own TOC, related links, and author bio.
    # Different drafting sessions used different class names for the same
    # thing (.bento-toc vs .signal-depth-navigator vs .nav-title), so match
    # broadly rather than a single fixed class.
    NAV_CLASS_MARKERS = ("bento", "signal-depth-navigator", "nav-title", "nav-abstract")

    def _is_nav_artifact(tag):
        classes = tag.get("class") or []
        if isinstance(classes, str):
            classes = classes.split()
        return any(any(m in cls for m in NAV_CLASS_MARKERS) for cls in classes)

    for tag in soup.find_all(_is_nav_artifact):
        tag.decompose()

    for heading in soup.find_all(["h2", "h3", "h4", "p"]):
        if heading.get_text(" ", strip=True) == "Signal Depth Navigator":
            heading.decompose()

    # Truncate everything from "Explore More" onward — in the Navigator
    # template this is immediately followed by the "Visit Us on:" promo
    # line and a duplicate About the Author section, none of which should
    # appear (this generator renders its own related-articles + author box).
    # Matched fuzzily (case-insensitive, ignoring emoji/punctuation) since
    # different drafting sessions phrased this heading slightly differently
    # ("Explore More", "🔍 Explore More", "Explore More ↗", etc.).
    EXPLORE_MORE_RE = re.compile(r"explore\s*more", re.I)
    for heading in soup.find_all(["h2", "h3", "h4"]):
        heading_text = heading.get_text(" ", strip=True)
        if EXPLORE_MORE_RE.search(heading_text) and len(heading_text) < 40:
            for sib in list(heading.find_next_siblings()):
                sib.decompose()
            heading.decompose()
            break

    # Drop any remaining back-btn / explore-btn links and their captions
    # (belt and suspenders, in case some slipped through without a matching
    # "Explore More" heading to anchor the truncation above — some older
    # Navigator variants embed these links with no heading at all)
    def _has_class(tag, names):
        classes = tag.get("class") or []
        if isinstance(classes, str):
            classes = classes.split()
        return any(any(n in cls for n in names) for cls in classes)

    for a in soup.find_all("a"):
        if _has_class(a, ("back-btn", "explore-btn")):
            parent = a.parent
            a.decompose()
            if parent and parent.name == "p" and not parent.get_text(strip=True):
                parent.decompose()

    for h4 in soup.find_all("h4"):
        if _has_class(h4, ("explore-desc",)):
            h4.decompose()

    # General safety net: any link pointing at a root-relative path that
    # isn't one of this site's known-good sections is almost certainly a
    # leftover Blogger-era URL (old teaser slugs, old category paths) that
    # will 404 on the new site structure. Unwrap it — keep the link text,
    # drop the dead link — rather than leaving a broken "Explore More"-style
    # link anywhere in the article.
    KNOWN_GOOD_PREFIXES = ("/articles/", "/category/", "/archive/", "/search/",
                            "/about/", "/contact/", "/privacy-policy/",
                            "/terms-and-conditions/", "/disclaimer/", "/#")
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("/") and not href.startswith(KNOWN_GOOD_PREFIXES):
            a.unwrap()

    # Drop a standalone "Visit Us on: https://..." promo line if it survived
    for div in soup.find_all(["div", "p"]):
        text = div.get_text(" ", strip=True)
        if text.lower().startswith("visit us on"):
            div.decompose()

    # Drop a duplicate "About the Author" section left in the raw content
    # (this generator always renders its own at the end of the article)
    for heading in soup.find_all(["h2", "h3"]):
        if heading.get_text(" ", strip=True) == "About the Author":
            nxt = heading.find_next_sibling()
            heading.decompose()
            if nxt and nxt.name == "p":
                nxt.decompose()

    # Drop hashtag-only paragraphs (this generator renders its own tag list
    # from the Blogger <category> labels instead)
    for p in soup.find_all("p"):
        text = p.get_text(" ", strip=True)
        if text and HASHTAG_LINE_RE.match(text.replace(" ", "")):
            p.decompose()

    # Final pass: remove now-empty paragraphs/divs left behind by the above
    for _ in range(2):
        for p in soup.find_all("p"):
            if not p.get_text(strip=True) and not p.find("img"):
                p.decompose()
        for div in soup.find_all("div"):
            if not div.get_text(strip=True) and not div.find("img"):
                div.decompose()

    return str(soup)


def dedupe_hero_image(html: str, hero_image_url: str) -> str:
    """The first image in a Blogger post's content is also promoted to the
    page's <figure class="article-media"> hero — drop that same image if it
    reappears as the first inline image in the body, otherwise it renders
    twice back-to-back."""
    if not html or not hero_image_url:
        return html

    soup = BeautifulSoup(html, "html.parser")
    first_img = soup.find("img")
    if first_img and first_img.get("src") == hero_image_url:
        container = first_img.find_parent(["div", "p"]) or first_img
        # only drop the wrapping container if it holds nothing but the image
        if container.name in ("div", "p") and container.get_text(strip=True) == "":
            container.decompose()
        else:
            first_img.decompose()

    return str(soup)
