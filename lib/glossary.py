"""
Interactive Knowledge Cards (Glossary) system.

Centralized term definitions live in data/glossary.json — that single file
is the one source of truth; editing a definition there updates every
article across the whole site on the next rebuild, and adding a new entry
automatically makes it clickable everywhere it appears, past articles
included, with zero per-article work.

This module does three things:
  1. load_glossary()      - read data/glossary.json into memory once
  2. resolve_guide_links() - for each term, look for an existing article
     whose title is substantially "about" that term and wire up an
     optional "Read Full Guide" link — computed fresh from the live
     article list on every build, so it stays correct as new articles are
     published without any manual mapping
  3. inject_glossary_links() - HTML-aware pass (BeautifulSoup, not naive
     regex) that wraps the FIRST occurrence of each matched term per
     article in an accessible <button class="gterm"> trigger, carefully
     avoiding tag/attribute internals, existing links, headings, code
     blocks, and the TOC.
  4. compile_glossary_payload() - build the small JSON blob the client-side
     widget fetches once per page load to render the tooltip/modal content.
"""
import json
import re
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString

DEFAULT_GLOSSARY_PATH = Path(__file__).resolve().parent.parent / "data" / "glossary.json"

# Only text inside these elements is eligible for term-linking. Skipping
# headings keeps the visual "voice" of an article's own heading typography
# clean; skipping table cells keeps comparison tables readable; list items
# and paragraphs are where the actual explanatory prose lives.
LINKABLE_TAGS = {"p", "li"}

# Never link inside these — links (avoid nesting interactive elements or
# re-linking inside an already-linked phrase), code/pre (verbatim content),
# and anything already inside a rendered glossary button.
SKIP_ANCESTORS = {"a", "code", "pre", "button", "script", "style", "h1", "h2", "h3", "h4", "nav"}


def load_glossary(path=DEFAULT_GLOSSARY_PATH):
    """Load the centralized glossary JSON. Returns {} (glossary disabled,
    site still builds fine) if the file is missing or malformed, so a typo
    in the JSON can never break the whole site build."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"WARNING: glossary disabled - could not load {path}: {e}")
        return {}

    # basic shape validation - skip (and warn about) any malformed entries
    # rather than letting one bad entry crash the whole build
    clean = {}
    for slug, entry in data.items():
        if not isinstance(entry, dict):
            continue
        if not entry.get("term") or not entry.get("definition") or not entry.get("match"):
            print(f"WARNING: skipping malformed glossary entry '{slug}' (missing term/definition/match)")
            continue
        clean[slug] = entry
    return clean


def resolve_guide_links(glossary, articles):
    """For each glossary term, find the best-matching published article to
    serve as its optional 'Read Full Guide' link, by substring-matching the
    term (or its longest alias) against article titles. Picks the most
    recently published match if more than one article qualifies. Returns a
    NEW dict (doesn't mutate the input) with a 'guide_url'/'guide_title' key
    added to matched entries.

    This runs fresh against the live article list on every build, so it
    self-updates as new articles are published - no manual term-to-article
    mapping to maintain."""
    resolved = {slug: dict(entry) for slug, entry in glossary.items()}

    # search titles with the longest match phrase first (most specific)
    for slug, entry in resolved.items():
        candidates = sorted(entry["match"], key=len, reverse=True)
        best_article = None
        for phrase in candidates:
            matches = [a for a in articles if phrase.lower() in a["title"].lower()]
            if matches:
                # most recently published wins if several articles qualify
                best_article = max(matches, key=lambda a: a["published"])
                break
        if best_article:
            entry["guide_url"] = f"/articles/{best_article['slug']}/"
            entry["guide_title"] = best_article["title"]

    return resolved


def _build_pattern(glossary):
    """One combined case-insensitive regex covering every match phrase
    across the whole glossary, longest phrase first so multi-word terms
    (e.g. 'large language model') win over any shorter phrase that happens
    to be a substring of it. Each alternative is tagged back to its slug
    via named groups is impractical at this scale, so instead we keep a
    parallel phrase->slug lookup and re-check on each match."""
    phrase_to_slug = {}
    all_phrases = []
    for slug, entry in glossary.items():
        for phrase in entry["match"]:
            phrase_to_slug[phrase.lower()] = slug
            all_phrases.append(phrase)

    # longest-first so overlapping phrases resolve to the most specific term
    all_phrases.sort(key=len, reverse=True)
    escaped = [re.escape(p) for p in all_phrases]
    pattern = re.compile(r"\b(" + "|".join(escaped) + r")\b", re.IGNORECASE)
    return pattern, phrase_to_slug


def _has_skip_ancestor(node):
    parent = node.parent
    while parent is not None:
        if getattr(parent, "name", None) in SKIP_ANCESTORS:
            return True
        parent = parent.parent
    return False


def inject_glossary_links(html_content, glossary, max_links=14):
    """Wrap the first in-article occurrence of each glossary term in an
    accessible trigger button. Only one occurrence per term is linked
    (repeated mentions stay plain text) to keep the article readable and
    non-intrusive, and the whole pass is capped at max_links per article
    for the same reason. Term detection walks actual parsed text nodes via
    BeautifulSoup, so it can never match inside a tag name, attribute, or
    an already-linked phrase."""
    if not html_content or not glossary:
        return html_content

    pattern, phrase_to_slug = _build_pattern(glossary)
    if not phrase_to_slug:
        return html_content

    soup = BeautifulSoup(html_content, "html.parser")
    used_slugs = set()
    links_made = 0

    for tag in soup.find_all(LINKABLE_TAGS):
        if links_made >= max_links:
            break
        # snapshot child text nodes before mutating (replacing a node while
        # iterating its parent's live children list would skip/duplicate)
        text_nodes = [n for n in tag.find_all(string=True, recursive=True)]
        for node in text_nodes:
            if links_made >= max_links:
                break
            if not isinstance(node, NavigableString) or not node.strip():
                continue
            if _has_skip_ancestor(node):
                continue

            text = str(node)
            match = pattern.search(text)
            if not match:
                continue

            slug = phrase_to_slug.get(match.group(1).lower())
            if not slug or slug in used_slugs:
                # term already linked once elsewhere in this article, or an
                # unrecognized alternation edge case - leave text as-is
                continue

            start, end = match.span(1)
            before, matched_text, after = text[:start], text[start:end], text[end:]

            button = soup.new_tag(
                "button",
                type="button",
                **{
                    "class": "gterm",
                    "data-gterm": slug,
                    "aria-haspopup": "dialog",
                    "aria-label": f"{matched_text} — glossary definition",
                },
            )
            button.string = matched_text

            new_nodes = []
            if before:
                new_nodes.append(NavigableString(before))
            new_nodes.append(button)
            if after:
                new_nodes.append(NavigableString(after))

            node.replace_with(*new_nodes)
            used_slugs.add(slug)
            links_made += 1

    return str(soup)


def compile_glossary_payload(glossary):
    """Build the minimal JSON payload shipped to the browser - only what
    the modal/tooltip actually needs to render, keeping the fetched file
    small and fast to load."""
    payload = {}
    for slug, entry in glossary.items():
        payload[slug] = {
            "term": entry["term"],
            "definition": entry["definition"],
            "icon": entry.get("icon", "📖"),
        }
        if entry.get("guide_url"):
            payload[slug]["guideUrl"] = entry["guide_url"]
            payload[slug]["guideTitle"] = entry.get("guide_title", "")
    return payload


def write_glossary_payload(glossary, output_path):
    payload = compile_glossary_payload(glossary)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    return len(payload)
