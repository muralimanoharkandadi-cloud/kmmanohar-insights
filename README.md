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

## Daily automatic updates (one-time setup)

New Blogger posts appear on the live site automatically, once a day,
with no manual step:

1. In Netlify: **Site settings → Build & deploy → Build hooks → Add build
   hook**. Name it e.g. `daily-rebuild`, copy the URL it gives you.
2. In GitHub: **Repo → Settings → Secrets and variables → Actions → New
   repository secret**. Name: `NETLIFY_BUILD_HOOK`. Value: the URL from
   step 1.
3. That's it — `.github/workflows/daily-rebuild.yml` pings that hook
   every day at 03:00 IST, Netlify rebuilds, `generate_site.py` re-fetches
   the live feed, and any new post gets its own full article page,
   correct category, and correct prev/next links automatically.

You can also trigger a rebuild manually anytime from the repo's
**Actions** tab → *Daily site rebuild* → *Run workflow*, or just publish
a new Blogger post and wait for the next scheduled run.

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
.github/workflows/daily-rebuild.yml   # scheduled Netlify rebuild trigger
```

## If categorization looks wrong for a specific article

Edit the keyword lists in `lib/categorize.py` — each cluster has a list
of keywords matched (case-insensitive, substring) against the post's
title, Blogger labels, and opening text, with title matches weighted
highest. No article data needs to change; just re-run the build.
