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

# Matches internal-link hrefs that look like a raw article TITLE got pasted
# in instead of a slug: a literal space, a %-escape (%20 etc.), an uppercase
# letter, or a parenthesis. Real generated slugs (see generate_site.py's
# slugify()) are always lowercase, hyphenated, alnum-only.
SUSPECT_HREF_RE = re.compile(r"[ %()]|[A-Z]")


def _normalize_internal_links(soup, warnings):
    """Root-relative-ize internal <a href> links.

    This generator's article/category pages are directory-style
    (/articles/some-slug/), so any internal link that is HAND-AUTHORED in
    Blogger content without a leading slash (e.g. href="some-slug/" instead
    of href="/some-slug/") resolves, in the browser, relative to the
    CURRENT page's path rather than site root. On a directory-style URL
    that silently chains: clicking through two such links in a row produces
    something like /articles/article-a/article-b/article-c/ instead of
    /articles/article-c/ — a real pattern seen in Netlify's 404 report.
    (External links, mailto:, tel:, and same-page #anchors are left alone.)

    Also flags — but does not silently rewrite — any href matching
    SUSPECT_HREF_RE, since a space/uppercase/parenthesis in an internal
    path is a strong sign the article's TITLE was pasted in as the href
    instead of its slug (also confirmed in the 404 report). These are
    collected into `warnings` so build() can print them the same way it
    already prints slug-collision and summary-mismatch warnings — worth a
    manual look rather than an auto-fix, since the correct target slug
    isn't always guessable from the title alone.
    """
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith(("http://", "https://", "mailto:", "tel:", "#")):
            continue

        if not href.startswith("/"):
            href = "/" + href
            a["href"] = href

        if SUSPECT_HREF_RE.search(href):
            warnings.append(href)

    return soup


def deep_clean(html: str, link_warnings: list | None = None) -> str:
    """Clean and normalize a single article's raw content HTML.

    `link_warnings`, if passed, is a list that suspicious internal hrefs
    (see _normalize_internal_links) get appended to, so the caller can
    print them alongside the other build-time warnings once, after all
    articles are processed, instead of per-article.
    """
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
    for heading in soup.find_all(["h2", "h3"]):
        if heading.get_text(" ", strip=True) == "Explore More":
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

    # Fix/flag any remaining internal links (in-body mentions, hand-pasted
    # "related article" links, etc.) that survived all the above — this
    # must run AFTER the explore-btn/back-btn/nav-artifact stripping above,
    # so it only ever touches genuine in-content links, not template debris
    # that's about to be deleted anyway.
    _normalize_internal_links(soup, link_warnings if link_warnings is not None else [])

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