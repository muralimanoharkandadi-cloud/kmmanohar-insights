#!/usr/bin/env python3
"""
Terminology scanner - crawls every article's text for candidate glossary
terms and reports the ones NOT already covered by data/glossary.json, so
new terms can be found systematically instead of by manually reading
articles one at a time.

USAGE
  # scan the committed feed.atom snapshot (fast, offline, what's in the repo)
  python3 tools/scan_terminology.py

  # scan the live Blogger feed instead (the full article history - needs
  # network access, which this sandboxed environment doesn't have, so run
  # this option from your own machine)
  python3 tools/scan_terminology.py --live

  # only show terms that appear in at least N articles (reduces noise from
  # one-off jargon that isn't worth a sitewide glossary entry - default 2)
  python3 tools/scan_terminology.py --min-articles 2

OUTPUT
  Prints a ranked report to the terminal AND writes
  tools/terminology_candidates.md with the same content, grouped into:
    1. "Term (ACRONYM)" pairs - highest-confidence signal, since this is
       exactly how a writer introduces a technical term in prose
    2. Standalone acronyms (2-6 capital letters) appearing 2+ times
    3. Chemical-formula-like tokens (e.g. PtSe2, MoS2, SiO2)
  Each candidate lists which article(s) it was found in and one example
  sentence of context, so a human (or a future Claude session) can decide
  which ones are actually worth writing a 50-100 word definition for.

This tool ONLY reads and reports - it never edits data/glossary.json
itself. Deciding which candidates deserve a real entry, and writing an
accurate plain-English definition, stays a deliberate editorial step.
"""
import argparse
import json
import re
import sys
import time
from collections import defaultdict
from pathlib import Path
from urllib.request import urlopen
from urllib.error import URLError
from xml.etree import ElementTree as ET

from bs4 import BeautifulSoup

REPO_ROOT = Path(__file__).resolve().parent.parent
GLOSSARY_PATH = REPO_ROOT / "data" / "glossary.json"
LOCAL_FEED = REPO_ROOT / "feed.atom"
LIVE_FEED_BASE = "https://kmmanohar1602.blogspot.com/feeds/posts/default?alt=atom"

ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}

# Common short acronyms that are either not really technical jargon, or
# already blindingly familiar to any reader - not worth flagging. Also
# includes leftover ALL-CAPS section-heading words from the site's own
# template skeleton (START HERE, LOOK AHEAD, FINAL TAKE, etc.) and other
# common English words that happen to get capitalized in headings, which
# the regex can't distinguish from real acronyms on letter-case alone.
ACRONYM_STOPLIST = {
    "AI", "US", "UK", "EU", "UN", "CEO", "CTO", "USA", "FAQ", "PDF", "URL",
    "API", "GDP", "R&D", "NASA", "ISRO",  # ISRO already a glossary entry
    # template/heading artifacts
    "KM", "START", "HERE", "LOOK", "AHEAD", "FINAL", "TAKE", "SIGNAL",
    "DEPTH", "CHECK", "MORE", "GLOBAL", "IMPACT", "INDIA", "WHAT", "JUST",
    "CORE", "FUTURE", "DOWN", "BEFORE", "NOW", "POINT", "THIS", "INSIDE",
    "RISKS", "SIMPLE", "WORKS", "WATCH", "REAL", "WHY",
    # common short English words that occasionally get capitalized
    "IT", "THE", "TO", "IN", "ON", "OF", "IS", "AS", "BY", "SO", "IF",
    "OR", "AT", "AN", "DO", "GO", "NO", "WE", "MY", "UP",
    # more template-heading / false-positive noise observed on a full
    # live-feed scan (250+ articles)
    "KEY", "TABLE", "TWIST", "ANGLE", "SHIFT", "NOT", "ARE", "VS", "DE",
    "INTRO", "JOIN", "ROAD", "III", "CO", "SO", "OK", "OFF", "ONE", "ON",
}


def load_glossary_match_terms():
    """All match phrases across the existing glossary, lowercased, so we
    can skip anything already covered."""
    if not GLOSSARY_PATH.exists():
        return set()
    with open(GLOSSARY_PATH, encoding="utf-8") as f:
        glossary = json.load(f)
    covered = set()
    for entry in glossary.values():
        for phrase in entry.get("match", []):
            covered.add(phrase.lower())
    return covered


def load_articles_from_local_feed():
    if not LOCAL_FEED.exists():
        print(f"ERROR: {LOCAL_FEED} not found", file=sys.stderr)
        sys.exit(1)
    tree = ET.parse(LOCAL_FEED)
    articles = []
    for entry in tree.getroot().findall("atom:entry", ATOM_NS):
        title_el = entry.find("atom:title", ATOM_NS)
        content_el = entry.find("atom:content", ATOM_NS)
        if content_el is None or content_el.text is None:
            continue
        articles.append({
            "title": (title_el.text or "").strip() if title_el is not None else "(untitled)",
            "html": content_el.text,
        })
    return articles


def load_articles_from_live_feed(max_results=25, sleep_between=0.5, max_pages=60):
    """Paginate through the live Blogger Atom feed. Needs outbound network
    access to blogspot.com, which the sandboxed environment this was
    written in does NOT have - run this flag from a machine with normal
    internet access.

    Prints progress after every page, since a full-history scan can take
    a minute or two and would otherwise look like it's hung. max_pages is
    a safety cap (60 pages * 25 = 1500 articles, far more than the current
    archive) so a misbehaving feed response can never loop forever."""
    articles = []
    start_index = 1
    for page_num in range(1, max_pages + 1):
        url = f"{LIVE_FEED_BASE}&max-results={max_results}&start-index={start_index}"
        try:
            with urlopen(url, timeout=20) as resp:
                data = resp.read()
        except URLError as e:
            print(f"ERROR fetching live feed (page {page_num}): {e}", file=sys.stderr)
            break
        tree = ET.fromstring(data)
        entries = tree.findall("atom:entry", ATOM_NS)
        if not entries:
            print(f"  page {page_num}: 0 entries - reached the end of the feed")
            break
        for entry in entries:
            title_el = entry.find("atom:title", ATOM_NS)
            content_el = entry.find("atom:content", ATOM_NS)
            if content_el is None or content_el.text is None:
                continue
            articles.append({
                "title": (title_el.text or "").strip() if title_el is not None else "(untitled)",
                "html": content_el.text,
            })
        print(f"  page {page_num}: {len(entries)} entries fetched ({len(articles)} total so far)")
        start_index += max_results
        time.sleep(sleep_between)
    else:
        print(f"WARNING: stopped at the {max_pages}-page safety cap - there may be more articles in the feed than this scan covered", file=sys.stderr)
    return articles


def article_plain_text(html):
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    return soup.get_text(" ", strip=True)


# "Term Phrase (ACRONYM)" - the strongest signal there is, since this is
# literally how a writer defines a term inline. Requires the phrase to
# start with a capital letter and the acronym to be 2-6 capital letters.
TERM_ACRONYM_RE = re.compile(
    r"\b([A-Z][A-Za-z\u2010-\u2015\-]*(?:\s+[A-Za-z][A-Za-z\u2010-\u2015\-]*){0,5})\s*\(([A-Z]{2,6})\)"
)

# Standalone acronyms anywhere in the text.
STANDALONE_ACRONYM_RE = re.compile(r"\b([A-Z]{2,6})\b")

# Chemical-formula-like tokens: an element-symbol-looking prefix followed
# by digits, e.g. PtSe2, MoS2, SiO2, Al2O3, GaN.
CHEM_FORMULA_RE = re.compile(r"\b([A-Z][a-z]?(?:\d[A-Za-z]?)?[A-Z][a-z]?\d*)\b")


def find_context_sentence(text, start, end, window=140):
    lo = max(0, start - window)
    hi = min(len(text), end + window)
    snippet = text[lo:hi].strip()
    return ("\u2026" if lo > 0 else "") + snippet + ("\u2026" if hi < len(text) else "")


def scan(articles, covered):
    term_acronym_hits = defaultdict(lambda: {"articles": set(), "context": None})
    standalone_acronym_hits = defaultdict(lambda: {"articles": set(), "context": None})
    chem_hits = defaultdict(lambda: {"articles": set(), "context": None})

    for art in articles:
        text = article_plain_text(art["html"])

        for m in TERM_ACRONYM_RE.finditer(text):
            phrase, acronym = m.group(1).strip(), m.group(2)
            key = f"{phrase} ({acronym})"
            if phrase.lower() in covered or acronym.lower() in covered:
                continue
            if acronym in ACRONYM_STOPLIST:
                continue
            entry = term_acronym_hits[key]
            entry["articles"].add(art["title"])
            if entry["context"] is None:
                entry["context"] = find_context_sentence(text, m.start(), m.end())

        for m in STANDALONE_ACRONYM_RE.finditer(text):
            acronym = m.group(1)
            if acronym in ACRONYM_STOPLIST or acronym.lower() in covered:
                continue
            entry = standalone_acronym_hits[acronym]
            entry["articles"].add(art["title"])
            if entry["context"] is None:
                entry["context"] = find_context_sentence(text, m.start(), m.end())

        for m in CHEM_FORMULA_RE.finditer(text):
            token = m.group(1)
            # needs at least one digit to look like a real formula, and
            # not be a plain capitalized English word
            if not any(c.isdigit() for c in token):
                continue
            if token.lower() in covered:
                continue
            entry = chem_hits[token]
            entry["articles"].add(art["title"])
            if entry["context"] is None:
                entry["context"] = find_context_sentence(text, m.start(), m.end())

    return term_acronym_hits, standalone_acronym_hits, chem_hits


def render_report(term_acronym_hits, standalone_acronym_hits, chem_hits, min_articles):
    lines = ["# Glossary terminology candidates", ""]
    lines.append(
        "Auto-generated by `tools/scan_terminology.py`. These are NOT "
        "glossary entries yet - review each one and add a proper 50-100 "
        "word definition to `data/glossary.json` for the ones worth "
        "explaining sitewide."
    )
    lines.append("")

    def section(title, hits, note=""):
        lines.append(f"## {title}")
        if note:
            lines.append(note)
        lines.append("")
        ranked = sorted(hits.items(), key=lambda kv: -len(kv[1]["articles"]))
        shown = [(k, v) for k, v in ranked if len(v["articles"]) >= min_articles]
        if not shown:
            lines.append("_(none meeting the --min-articles threshold)_")
        for key, data in shown:
            arts = sorted(data["articles"])
            arts_display = ", ".join(arts[:3]) + (f", +{len(arts) - 3} more" if len(arts) > 3 else "")
            lines.append(f"- **{key}** — seen in {len(arts)} article(s): {arts_display}")
            lines.append(f"  > {data['context']}")
        lines.append("")

    section(
        "1. \"Term (ACRONYM)\" pairs — highest confidence",
        term_acronym_hits,
        "The article itself introduces the term next to its acronym, exactly the pattern a glossary should cover.",
    )
    section(
        "2. Standalone acronyms",
        standalone_acronym_hits,
        "No inline expansion found nearby — worth a quick check on what they stand for before writing a definition.",
    )
    section(
        "3. Chemical-formula-like tokens",
        chem_hits,
        "Likely materials/compounds (e.g. PtSe2, MoS2). Verify each is a real formula, not a false positive.",
    )
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--live", action="store_true", help="scan the live Blogger feed instead of the local feed.atom snapshot")
    parser.add_argument("--min-articles", type=int, default=2, help="only report terms appearing in at least N articles (default 2)")
    args = parser.parse_args()

    covered = load_glossary_match_terms()
    print(f"Loaded {len(covered)} existing match phrases from {GLOSSARY_PATH.relative_to(REPO_ROOT)}")

    if args.live:
        print("Fetching live Blogger feed (this needs network access to blogspot.com)...")
        articles = load_articles_from_live_feed()
    else:
        print(f"Loading local snapshot: {LOCAL_FEED.relative_to(REPO_ROOT)}")
        articles = load_articles_from_local_feed()
    print(f"Scanning {len(articles)} article(s)...")

    term_acronym_hits, standalone_acronym_hits, chem_hits = scan(articles, covered)
    report = render_report(term_acronym_hits, standalone_acronym_hits, chem_hits, args.min_articles)

    out_path = REPO_ROOT / "tools" / "terminology_candidates.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")
    print(f"\nWrote report to {out_path.relative_to(REPO_ROOT)}\n")
    print(report)


if __name__ == "__main__":
    main()
