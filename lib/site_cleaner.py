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

    # Remove the Signal Depth Navigator's TOP BOX ("3 Life Signals You
    # Shouldn't Ignore") and BOTTOM BOX ("Tweak for the Day") content blocks.
    # These are teal callout boxes in the Blogger template; once this
    # generator strips inline styles, they'd otherwise survive as bare
    # unstyled paragraphs sitting awkwardly in the middle of the article
    # (right after the opening hook, and again after the hero image).
    #
    # This is written defensively because different drafting sessions
    # produced inconsistent/sometimes malformed markup here - in some posts
    # the box heading ends up merged into the same block as the preceding
    # hook quote (a missing closing tag upstream), so a naive "decompose the
    # whole containing <p>/<div>" approach can either fail to match at all
    # or, worse, delete real content sharing that block. Instead: walk up
    # past inline wrapper tags to find the nearest block container, only
    # decompose that container wholesale if it holds nothing substantial
    # besides the marker text itself, and locate the following Health:/
    # Finance:/Relationships: lines via forward document-order traversal
    # (find_next) rather than assuming a strict parent/sibling relationship.
    LIFE_SIGNAL_MARKERS = ("3 Life Signals You Shouldn't Ignore", "Tweak for the Day")
    INLINE_WRAPPERS = ("strong", "em", "b", "i", "span", "font", "u")

    for marker in LIFE_SIGNAL_MARKERS:
        while True:
            node = soup.find(string=lambda t: t and marker in t)
            if node is None:
                break

            block = node.parent
            while block is not None and getattr(block, "name", None) in INLINE_WRAPPERS:
                block = block.parent

            # Collect up to 3 following Health:/Finance:/Relationships: lines,
            # walking forward in document order regardless of nesting depth.
            removed_items = 0
            search_from = block if block is not None else node
            cursor = search_from.find_next(["p", "div", "li"]) if hasattr(search_from, "find_next") else None
            item_candidates = []
            while cursor is not None and removed_items < 3:
                item_text = cursor.get_text(" ", strip=True)
                if any(m in item_text for m in ("Health:", "Finance:", "Relationships:")):
                    item_candidates.append(cursor)
                    removed_items += 1
                    cursor = cursor.find_next(["p", "div", "li"])
                else:
                    break
            for item in item_candidates:
                item.decompose()

            # Remove the heading itself. If its block container holds
            # nothing but the marker (plus a short emoji/label prefix),
            # remove the whole container; otherwise it's sharing space with
            # unrelated real content (e.g. a merged hook quote), so only
            # strip the marker text run and leave the rest intact.
            if block is not None and block.name in ("div", "p", "li", "h2", "h3", "h4"):
                block_text = block.get_text(" ", strip=True)
                if len(block_text) <= len(marker) + 20:
                    block.decompose()
                else:
                    # The marker is merged into the same text node as real
                    # content (e.g. a missing closing tag upstream fused the
                    # hook quote and the box heading together) - surgically
                    # remove just the marker substring rather than deleting
                    # the whole node, which would take the real text with it.
                    cleaned = str(node).replace(marker, "").strip()
                    if cleaned:
                        node.replace_with(cleaned)
                    else:
                        node.extract()
            else:
                cleaned = str(node).replace(marker, "").strip()
                if cleaned:
                    node.replace_with(cleaned)
                else:
                    node.extract()

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

    # General safety net: unwrap any link that isn't demonstrably safe.
    # Blogger content carries three kinds of dangerous hrefs left over from
    # the old site structure:
    #   1. root-relative paths to old pages ("/some-old-slug/")
    #   2. bare relative paths with NO leading slash ("some-slug/") - these
    #      resolve against the CURRENT article's URL, which is how you get
    #      garbage nested paths like /articles/post-a/post-b/post-c/
    #   3. absolute URLs pointing at this site's own old page structure
    # Genuine external links (to research papers, news sources, etc.),
    # mailto:, and same-page "#anchor" links are left untouched.
    KNOWN_GOOD_PREFIXES = ("/articles/", "/category/", "/archive/", "/search/",
                            "/about/", "/contact/", "/privacy-policy/",
                            "/terms-and-conditions/", "/disclaimer/", "/#")
    SITE_DOMAIN = "kmmanoharinsights.netlify.app"

    def _is_safe_href(href):
        href = href.strip()
        if href.startswith("#") or href.startswith("mailto:") or href.startswith("tel:"):
            return True
        if SITE_DOMAIN in href:
            # self-referential absolute link - only safe if it matches a
            # known-good current path
            path = href.split(SITE_DOMAIN, 1)[1]
            return path in ("", "/") or path.startswith(KNOWN_GOOD_PREFIXES)
        if href.startswith("http://") or href.startswith("https://"):
            return True  # genuine external reference - keep as-is
        if href.startswith("/"):
            return href.startswith(KNOWN_GOOD_PREFIXES)
        # anything else is a bare relative path with no leading slash or
        # protocol - always unsafe, this is the main bug class
        return False

    for a in soup.find_all("a", href=True):
        if not _is_safe_href(a["href"]):
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
