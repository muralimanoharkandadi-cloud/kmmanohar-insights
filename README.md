# K M Manohar Insights — Static Site Generator

Builds the full self-hosted site (homepage, 5 category pages, archive,
search, and one full article page per Blogger post) from the live
Blogger Atom feed. No more teaser pages redirecting out to Blogspot —
every article is rendered in full, in this site's own design.

## How it works

`generate_site.py` is the entire pipeline:

1. Fetches your Blogger Atom feed (live URL, paginated automatically)
2. Cleans each post's HTML — strips ChatGPT/Word export junk, legacy
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

1. In Netlify: **Site settings → Build & deploy → Continuous deployment**,
   connect this repo. Build command and publish directory are already
   configured in `netlify.toml` (`python3 generate_site.py` → `dist`).
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

Netlify reads this schedule straight from the repo on every deploy —
no extra setup, no build hook, no GitHub secret needed. When it fires,
Netlify rebuilds the site, `generate_site.py` re-fetches the live feed,
and any new post gets its own full article page, correct category, and
correct prev/next links automatically.

You can check recent runs and the next scheduled time anytime under
**Netlify dashboard → Logs & metrics → Functions → scheduled-rebuild**.

To change the time, edit the `schedule` line above (cron syntax, in
UTC) and push — no dashboard setting to touch separately.

> **Note:** an earlier version of this project used a GitHub Actions
> workflow (`daily-rebuild.yml`) pinging a Netlify build hook instead.
> That approach has been disabled in favor of the Netlify Scheduled
> Function above, since GitHub Actions cron was landing hours late
> under load. The old workflow file is disabled but left in the repo
> for reference.

## Files

```
generate_site.py          # the whole pipeline — read this first
lib/
  parser.py                # Blogger Atom feed → article dicts (existing)
  content_cleaner.py        # first-pass HTML cleaning (existing)
  categorize.py             # NEW — labels/title → one of 5 clusters
  site_cleaner.py            # NEW — second-pass deep clean + hero image dedup
styles.css                  # site design system (unchanged, plus article-body
                              # extensions for long-form content: TOC, tags,
                              # explore-more, author card)
app.js                       # unchanged
netlify.toml                 # build command + publish dir
requirements.txt              # beautifulsoup4, lxml
.github/workflows/daily-rebuild.yml   # legacy rebuild trigger, disabled — see "Daily automatic updates" above
```

## If categorization looks wrong for a specific article

Edit the keyword lists in `lib/categorize.py` — each cluster has a list
of keywords matched (case-insensitive, substring) against the post's
title, Blogger labels, and opening text, with title matches weighted
highest. No article data needs to change; just re-run the build.
