# K M Manohar Insights â€” Static Site Generator

Builds the full self-hosted site (homepage, 5 category pages, archive,
search, and one full article page per Blogger post) from the live
Blogger Atom feed. No more teaser pages redirecting out to Blogspot â€”
every article is rendered in full, in this site's own design.

## How it works

`generate_site.py` is the entire pipeline:

1. Fetches your Blogger Atom feed (live URL, paginated automatically)
2. Cleans each post's HTML â€” strips ChatGPT/Word export junk, legacy
   inline font-family spans, and (for posts already recoded into the
   Signal Depth Navigator bento format) all of that template's own
   TOC/back-btn/explore-btn/About Author markup, since this generator
   renders its own versions of all of that
3. Assigns each post to one of 5 clusters (Digital Intelligence,
   Frontier Technologies, Human Future, Sustainable Future, India &
   Society) based on its Blogger labels + title
4. Renders every page and writes the whole site into `dist/`

## Local testing

```bash
pip install -r requirements.txt

# Test against the small local feed.atom snapshot (offline, fast):
FEED_SOURCE=feed.atom python3 generate_site.py

# Test against the real, full, live feed (needs internet access):
python3 generate_site.py

# Preview the output:
cd dist && python3 -m http.server 8000
# open http://localhost:8000
```

## Netlify setup (one-time)

1. In Netlify: **Site settings â†’ Build & deploy â†’ Continuous deployment**,
   connect this repo. Build command and publish directory are already
   configured in `netlify.toml` (`python3 generate_site.py` â†’ `dist`).
2. Trigger a deploy once to confirm it builds cleanly.

## Daily automatic updates

New Blogger posts appear on the live site automatically, once a day,
with no manual step:

The rebuild is triggered by a **Netlify Scheduled Function**
(`netlify/functions/scheduled-rebuild`), configured directly in
`netlify.toml`:

```toml
[functions."scheduled-rebuild"]
  schedule = "20 5 * * *"   # 10:50 AM IST daily
```

Netlify reads this schedule straight from the repo on every deploy â€”
no extra setup, no build hook, no GitHub secret needed. When it fires,
Netlify rebuilds the site, `generate_site.py` re-fetches the live feed,
and any new post gets its own full article page, correct category, and
correct prev/next links automatically.

The time is set to land shortly after the usual publish slot (posts go
up between 10:23 and 10:35 IST) and, just as importantly, before social
media promotion starts around 11:00-11:15 IST â€” the article needs to be
live on-site by then. This briefly moved to 11:50 AM on 2026-09-18 after
a rebuild running only 19 minutes post-publish missed that day's article
(Google's frontend cache in front of the Blogger feed can serve a
pre-publish snapshot that close to publishing), but that was a stopgap,
not the real fix: `generate_site.py`'s feed fetch now sends explicit
no-cache headers plus a cache-busting query param on every request, and
`lib/parser.py`'s `get_slug()` no longer silently drops a post just
because Blogger assigned it the generic default `blog-post` permalink
(which was the actual cause of that specific miss). With those fixed,
the schedule moved back to 10:50 AM. If a similar miss recurs, check
those two fixes before reaching for a schedule delay again.

You can check recent runs and the next scheduled time anytime under
**Netlify dashboard â†’ Logs & metrics â†’ Functions â†’ scheduled-rebuild**.

To change the time, edit the `schedule` line above (cron syntax, in
UTC) and push â€” no dashboard setting to touch separately.

> **Note:** an earlier version of this project used a GitHub Actions
> workflow (`daily-rebuild.yml`) pinging a Netlify build hook instead.
> That approach has been disabled in favor of the Netlify Scheduled
> Function above, since GitHub Actions cron was landing hours late
> under load. The old workflow file is disabled but left in the repo
> for reference.

## Files

```
generate_site.py          # the whole pipeline â€” read this first
lib/
  parser.py                # Blogger Atom feed â†’ article dicts (existing)
  content_cleaner.py        # first-pass HTML cleaning (existing)
  categorize.py             # NEW â€” labels/title â†’ one of 5 clusters
  site_cleaner.py            # NEW â€” second-pass deep clean + hero image dedup
styles.css                  # site design system (unchanged, plus article-body
                              # extensions for long-form content: TOC, tags,
                              # explore-more, author card)
app.js                       # unchanged
netlify.toml                 # build command + publish dir
requirements.txt              # beautifulsoup4, lxml
.github/workflows/daily-rebuild.yml   # legacy rebuild trigger, disabled â€” see "Daily automatic updates" above
```

## If categorization looks wrong for a specific article

Edit the keyword lists in `lib/categorize.py` â€” each cluster has a list
of keywords matched (case-insensitive, substring) against the post's
title, Blogger labels, and opening text, with title matches weighted
highest. No article data needs to change; just re-run the build.
