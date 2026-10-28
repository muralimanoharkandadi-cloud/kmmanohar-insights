#!/usr/bin/env python3
"""
validate_article.py — pre-publish QA check for K M Manohar Insights articles.

Catches every structural bug pattern found so far in the Signal Depth
Navigator template before the article ever reaches Blogger:

  1. Too few <h2> sections (< 2)         -> Netlify's TOC/back-links won't render
  2. Split/duplicate title <h1> tags      -> becomes a broken 2-item TOC
  3. Separator <div> wrapping real content -> forces the whole block center-aligned
  4. Unscoped bento/kmi-* CSS              -> collides with Blogger's mobile theme
  5. Orphaned "Explore More"/"Related Articles" heading -> no links under it
  6. Leftover ChatGPT/export junk           -> data-start/data-end/data-section-id,
                                               huge div.flex UI scaffolding
  7. <a name="sN"> anchors missing id+aria-hidden (recommended, not required)
  8. explore-btn links still using "#" placeholder hrefs

Usage:
    python validate_article.py path/to/draft.html

Exit code 0 = clean. Exit code 1 = problems found (see printed report).
"""

import sys
import re
from bs4 import BeautifulSoup


def check_heading_count(soup, report):
    h1s = soup.find_all("h1")
    h2s = soup.find_all("h2")
    if len(h1s) > 1:
        report.fail(
            f"Found {len(h1s)} <h1> tags — likely a split/duplicate title. "
            f"The site auto-converts every <h1> to <h2>, so this becomes a "
            f"broken multi-item TOC entry instead of one clean heading."
        )
    real_h2_count = len(h2s) + (1 if len(h1s) == 1 else 0)
    if real_h2_count < 2:
        report.fail(
            f"Only {real_h2_count} <h2>-level heading(s) found. Netlify's "
            f"generator needs at least 2 to render a TOC or any back-to-TOC "
            f"links at all — check whether real sections got coded as <h3> "
            f"instead of <h2>."
        )
    else:
        report.ok(f"{real_h2_count} <h2>-level section headings found.")


def check_separator_divs(soup, report):
    bad = []
    for i, div in enumerate(soup.find_all("div", class_="separator")):
        # A healthy separator div contains only an <a>/<img>/<span>/<br> wrapping
        # the image — nothing structural like <p>, <h2>, <h3>, <ul>, <hr>.
        if div.find(["p", "h2", "h3", "h4", "ul", "ol", "hr"]):
            bad.append(i)
    if bad:
        report.fail(
            f"{len(bad)} separator div(s) contain real content (paragraphs, "
            f"headings, lists) instead of just an image — this traps that "
            f"content in Blogger's forced center-align CSS. Check that every "
            f"<div class=\"separator\"> closes immediately after its <img>, "
            f"before the next paragraph starts."
        )
    else:
        n = len(soup.find_all("div", class_="separator"))
        report.ok(f"All {n} separator div(s) wrap only images — no centering risk.")


def check_css_scoping(soup, report):
    style = soup.find("style")
    if not style or not style.string:
        report.warn("No <style> block found — skipping CSS scoping check.")
        return
    css = style.string
    has_wrapper = soup.find("article", class_="kmi-article") is not None
    # crude check: does every non-@media, non-comment selector line start with .kmi-article?
    unscoped = []
    for line in css.split("\n"):
        s = line.strip()
        if not s or s.startswith("@media") or s == "}" or s.startswith("/*"):
            continue
        if "{" in s:
            sel = s.split("{", 1)[0].strip()
            selectors = [x.strip() for x in sel.split(",")]
            for sub in selectors:
                if sub and not sub.startswith(".kmi-article"):
                    unscoped.append(sub)
    if unscoped:
        report.fail(
            f"Found {len(unscoped)} unscoped CSS selector(s) not prefixed with "
            f".kmi-article (e.g. {unscoped[0]!r}). Bare class names like "
            f".bento-item collide with Blogger's own mobile theme CSS and can "
            f"cause the bento boxes to stretch/balloon on mobile."
        )
    elif not has_wrapper:
        report.fail(
            "CSS is scoped under .kmi-article, but no <article class=\"kmi-article\"> "
            "wrapper was found around the content — the scoping won't take effect."
        )
    else:
        report.ok("CSS is properly scoped under .kmi-article, and the wrapper is present.")


def check_explore_more(soup, report):
    explore_more_re = re.compile(r"explore\s*more|related\s*articles", re.I)
    found_heading = False
    for heading in soup.find_all(["h2", "h3", "h4"]):
        text = heading.get_text(" ", strip=True)
        if explore_more_re.search(text) and len(text) < 40:
            found_heading = True
            has_links = False
            placeholder_links = 0
            for sib in heading.find_next_siblings():
                is_own_desc = sib.name == "h4" and "explore-desc" in (sib.get("class") or [])
                if sib.name in ("h1", "h2", "h3") or (sib.name == "h4" and not is_own_desc):
                    break
                # Accept any real link here, not just .explore-btn — some articles
                # use plain <a href> markup instead of the styled pill class.
                links = sib.find_all("a", href=True) if sib.name != "a" else (
                    [sib] if sib.get("href") else []
                )
                for a in links:
                    has_links = True
                    if a.get("href", "").strip() in ("#", ""):
                        placeholder_links += 1
            if not has_links:
                report.fail(
                    f'"{text}" heading has no explore-btn links after it — '
                    f"it'll render as an orphaned heading with nothing underneath."
                )
            elif placeholder_links:
                report.warn(
                    f'"{text}" has {placeholder_links} link(s) still using a "#" '
                    f"placeholder href — fine for a draft, but fill in real URLs "
                    f"before publishing."
                )
            else:
                report.ok(f'"{text}" section has real links, all populated.')
    if not found_heading:
        report.warn("No Explore More / Related Articles section found (may be intentional).")


def check_junk_markup(soup, report):
    html = str(soup)
    junk_attrs = ["data-start=", "data-end=", "data-section-id=", "data-message-author-role="]
    found = [a for a in junk_attrs if a in html]
    if found:
        report.fail(
            f"Leftover ChatGPT/export junk attributes found: {', '.join(a.rstrip('=') for a in found)}. "
            f"Strip these before publishing."
        )
    else:
        report.ok("No leftover export junk attributes found.")

    scaffolding = soup.find("div", class_=lambda c: c and "flex" in c and "flex-col" in c)
    if scaffolding:
        report.fail(
            "Found leftover ChatGPT UI div scaffolding (class contains 'flex flex-col') "
            "— usually appears wrapping pasted Explore More links. Replace with clean <p><a>...</a></p> markup."
        )
    else:
        report.ok("No leftover ChatGPT UI div scaffolding found.")


def check_anchor_format(soup, report):
    old_style = [a for a in soup.find_all("a", attrs={"name": True}) if not a.get("id")]
    if old_style:
        report.warn(
            f"{len(old_style)} anchor(s) use <a name=\"sN\"> without a matching id/aria-hidden "
            f"— not broken, but the current template uses "
            f'<a aria-hidden="true" id="sN" name="sN"></a> for accessibility. Consider updating.'
        )
    else:
        report.ok("All section anchors use the current dual id+name+aria-hidden format.")


class Report:
    def __init__(self):
        self.failures = []
        self.warnings = []
        self.oks = []

    def fail(self, msg):
        self.failures.append(msg)

    def warn(self, msg):
        self.warnings.append(msg)

    def ok(self, msg):
        self.oks.append(msg)

    def print_and_exit(self):
        print("=" * 70)
        print("SIGNAL DEPTH NAVIGATOR — PRE-PUBLISH VALIDATION REPORT")
        print("=" * 70)
        if self.oks:
            print("\nPASSED:")
            for m in self.oks:
                print(f"  \u2713 {m}")
        if self.warnings:
            print("\nWARNINGS (review before publishing):")
            for m in self.warnings:
                print(f"  \u26a0 {m}")
        if self.failures:
            print("\nFAILURES (fix before publishing):")
            for m in self.failures:
                print(f"  \u2717 {m}")
            print(f"\n{len(self.failures)} failure(s), {len(self.warnings)} warning(s). NOT ready to publish.")
            sys.exit(1)
        else:
            suffix = f" ({len(self.warnings)} warning(s) to review)" if self.warnings else ""
            print(f"\nAll checks passed{suffix}. Looks ready to publish.")
            sys.exit(0)


def main():
    if len(sys.argv) != 2:
        print("Usage: python validate_article.py path/to/draft.html")
        sys.exit(2)
    path = sys.argv[1]
    try:
        html = open(path, encoding="utf-8").read()
    except FileNotFoundError:
        print(f"File not found: {path}")
        sys.exit(2)

    soup = BeautifulSoup(html, "html.parser")
    report = Report()

    check_heading_count(soup, report)
    check_separator_divs(soup, report)
    check_css_scoping(soup, report)
    check_explore_more(soup, report)
    check_junk_markup(soup, report)
    check_anchor_format(soup, report)

    report.print_and_exit()


if __name__ == "__main__":
    main()
