from bs4 import BeautifulSoup, Comment
import re

CHATGPT_ATTRS = [
    "data-message-author-role",
    "data-message-model-slug",
    "data-message-id",
    "data-turn",
    "data-turn-id",
    "data-testid",
]
BLOGGER_ATTRS = [
    "data-original-width",
    "data-original-height",
    "data-start",
    "data-end",
    "data-section-id",
]


def clean_content(html: str) -> str:
    if not html:
        return ""

    soup = BeautifulSoup(html, "html.parser")

    # Remove <!--more-->
    for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
        if "more" in comment.lower():
            comment.extract()

    # Remove ChatGPT wrapper elements
    for tag in soup.find_all(True):
        attrs = tag.attrs or {}
        if any(attr in attrs for attr in CHATGPT_ATTRS):
            tag.decompose()
           
            

    # Remove empty paragraphs
    for p in soup.find_all("p"):
        text = p.get_text().replace("\xa0", "").strip()
        if not text and not p.find("img") and not p.find("br"):
            p.decompose()
    # Remove empty spans
    for span in soup.find_all("span"):
        if not span.get_text(strip=True) and not span.find("img"):
            span.decompose()
    # Remove empty divs
    for div in soup.find_all("div"):
        if not div.get_text(strip=True) and not div.find("img"):
            div.decompose()
    # Remove empty bold tags
    for tag in soup.find_all(["b", "strong"]):
        if not tag.get_text(strip=True) and not tag.find("img"):
            tag.decompose()
    # Unwrap redundant spans
    for span in soup.find_all("span"):
        if not span.attrs:
            span.unwrap()        

    # Convert h1 to h2
    for h in soup.find_all("h1"):
        h.name = "h2"

    # Remove duplicate headings
    previous = None
    for tag in soup.find_all(["h2", "h3", "h4"]):
        text = tag.get_text(" ", strip=True)

        if text == previous:
            tag.decompose()
        else:
            previous = text

    # Lazy-load images
    for img in soup.find_all("img"):
        img["loading"] = "lazy"
        img["decoding"] = "async"
            # Remove Blogger metadata attributes
    for tag in soup.find_all(True):
        for attr in BLOGGER_ATTRS:
            tag.attrs.pop(attr, None)
    # Rewrite Blogger article links to local links
    for a in soup.find_all("a", href=True):
        href = a["href"]

        m = re.search(
            r"https?://(?:www\.)?kmmanohar1602\.blogspot\.com/\d{4}/\d{2}/([^/?#]+)\.html",
            href,
            re.I,
        )

        if m:
            a["href"] = f"/{m.group(1)}/"

    return str(soup)