#!/usr/bin/env python3
"""Build Dank Recovery News.

Write each story as news-src/<slug>.md:

    ---
    title: Headline goes here
    dek: One-sentence summary shown under the headline and in share previews.
    date: 2026-11-22
    time: 09:30   (optional, Central time the story went up; Google likes an exact time)
    type: news    (optional: news, opinion, podcast or sponsored; default is news)
    author: Timothy Kavanagh
    updated: optional note shown at the top, e.g. a correction
    modified: optional date of the last real change, e.g. 2026-11-25
    ---
    Story body in Markdown.

Then run:  python3 tools/build_news.py

It writes, for every story:
  news/<slug>/index.html   the article page, with X and Facebook share tags
  news/<slug>/card.png     the 1200x630 image X and Facebook show in the preview
and rebuilds the news front page (newest first), the Opinion and Podcasts
section pages (only when they have stories), news/feed.xml (RSS),
sitemap.xml (every page) and news-sitemap.xml (stories from the last 2 days,
which is what Google News reads).

The About, Ethics and Privacy pages are built from news-src/pages/<slug>.md.
Files whose name starts with "_" are skipped (drafts).
"""
import datetime as dt
import html
import json
import re
import sys
from email.utils import format_datetime
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo

import markdown
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "news-src"
PAGES = SRC / "pages"
OUT = ROOT / "news"
FONTS = Path(__file__).resolve().parent / "fonts"
SITE = "https://dankrecovery.com"
X_HANDLE = "@dankrecovery"
DEFAULT_AUTHOR = "Timothy Kavanagh"
AUTHOR_URL = f"{SITE}/news/about/#timothy-kavanagh"
AUTHOR_BLURB = "Timothy Kavanagh is the editor of Dank Recovery News. He has worked in addiction recovery since 2013."
PUBLICATION = "Dank Recovery News"
TAGLINE = "Recovery news and trends, and what's happening in the fellowship worldwide."
TZ = ZoneInfo("America/Chicago")
NEWS_SITEMAP_DAYS = 2
SIGNUP_ENDPOINT = "https://script.google.com/macros/s/AKfycbyEt3vbVzJD7ltwRnEnwiYEEIGz453PrwWQ8f9dHvfg3XHEx8GCQePpcfzzDBb7BaFuDw/exec"

# type: (label on the story, section page slug or None, schema.org type)
TYPES = {
    "news": ("News", None, "NewsArticle"),
    "opinion": ("Opinion", "opinion", "OpinionNewsArticle"),
    "podcast": ("Podcasts", "podcasts", "NewsArticle"),
    "sponsored": ("Sponsored", None, "AdvertiserContentArticle"),
}
SECTION_BLURB = {
    "opinion": "Opinion pieces. These are the writer's views, not news reports.",
    "podcasts": "What happened on the recovery podcasts worth your time.",
}

INK, BONE, ASH, RULE, BRASS = "#0d0c0b", "#ece4d2", "#a39c8c", "#37322b", "#c9a24a"

e = html.escape


def split_header(path):
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", text, re.S)
    if not m:
        sys.exit(f"{path.name}: missing the --- header block at the top")
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip().lower()] = v.strip()
    return meta, m.group(2)


def md(text):
    return markdown.markdown(text, extensions=["extra", "smarty"])


def parse(path):
    meta, body = split_header(path)
    for k in ("title", "dek", "date"):
        if not meta.get(k):
            sys.exit(f"{path.name}: needs a '{k}:' line")
    try:
        meta["date_obj"] = dt.date.fromisoformat(meta["date"])
    except ValueError:
        sys.exit(f"{path.name}: date must look like 2026-11-22")
    # exact publish time (Central) if given; otherwise date only
    meta["dt"] = None
    meta["iso"] = meta["date_obj"].isoformat()
    if meta.get("time"):
        try:
            t = dt.time.fromisoformat(meta["time"])
        except ValueError:
            sys.exit(f"{path.name}: time must look like 09:30")
        meta["dt"] = dt.datetime.combine(meta["date_obj"], t, TZ)
        meta["iso"] = meta["dt"].isoformat(timespec="seconds")
    meta["modified_iso"] = None
    if meta.get("modified"):
        try:
            meta["modified_iso"] = dt.date.fromisoformat(meta["modified"]).isoformat()
        except ValueError:
            sys.exit(f"{path.name}: modified must look like 2026-11-25")
    meta["type"] = (meta.get("type") or "news").lower()
    if meta["type"] not in TYPES:
        sys.exit(f"{path.name}: type must be one of {', '.join(TYPES)}")
    meta["kicker"] = TYPES[meta["type"]][0]
    meta["slug"] = path.stem
    meta["author"] = meta.get("author") or DEFAULT_AUTHOR
    meta["body_html"] = md(body)
    meta["url"] = f"{SITE}/news/{meta['slug']}/"
    return meta


def nice_date(d):
    return d.strftime("%B %-d, %Y")


def nice_when(s):
    """November 23, 2026 · 9:30 a.m. CT"""
    out = nice_date(s["date_obj"])
    if s["dt"]:
        ampm = "a.m." if s["dt"].hour < 12 else "p.m."
        out += f" · {s['dt'].strftime('%-I:%M')} {ampm} CT"
    return out


# ---------- share card ----------

def wrap(draw, text, font, width):
    words, lines, line = text.split(), [], ""
    for w in words:
        trial = (line + " " + w).strip()
        if draw.textlength(trial, font=font) <= width:
            line = trial
        else:
            if line:
                lines.append(line)
            line = w
    if line:
        lines.append(line)
    return lines


def make_card(meta, dest):
    W, H, PAD = 1200, 630, 72
    img = Image.new("RGB", (W, H), INK)
    d = ImageDraw.Draw(img)
    mono = ImageFont.truetype(str(FONTS / "IBMPlexMono-Medium.ttf"), 26)

    # top label and rule
    label = "DANK RECOVERY NEWS"
    if meta.get("type") in ("opinion", "sponsored"):
        label += f"  ·  {meta['kicker'].upper()}"
    d.text((PAD, PAD - 6), label, font=mono, fill=BRASS)
    d.line([(PAD, PAD + 40), (W - PAD, PAD + 40)], fill=RULE, width=2)

    # headline: biggest size that fits in 4 lines
    box_w, box_h = W - PAD * 2, H - PAD * 2 - 150
    for size in range(78, 34, -2):
        font = ImageFont.truetype(str(FONTS / "AlfaSlabOne-Regular.ttf"), size)
        lines = wrap(d, meta["title"], font, box_w)
        lh = int(size * 1.12)
        if len(lines) <= 4 and lh * len(lines) <= box_h:
            break
    y = PAD + 72
    for ln in lines:
        d.text((PAD, y), ln, font=font, fill=BONE)
        y += lh

    # bottom rule, date, seal
    d.line([(PAD, H - PAD - 60), (W - PAD, H - PAD - 60)], fill=RULE, width=2)
    foot = "DANKRECOVERY.COM/NEWS"
    if meta.get("date_obj"):
        foot = f"{nice_date(meta['date_obj']).upper()}  ·  {foot}"
    d.text((PAD, H - PAD - 30), foot, font=mono, fill=ASH)
    logo = ROOT / "logo.jpg"
    if logo.exists():
        s = 96
        seal = ImageOps.fit(Image.open(logo).convert("RGB"), (s, s))
        mask = Image.new("L", (s, s), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, s, s), fill=255)
        img.paste(seal, (W - PAD - s, H - PAD - 60 - s // 2 - 2 + 30), mask)
    img.save(dest, optimize=True)


# ---------- shared page parts ----------

def header(current, sections):
    """Newspaper nameplate plus the section bar. `sections` = section slugs that have stories."""
    def link(href, label, key):
        cur = ' aria-current="page"' if key == current else ""
        return f'<a href="{href}"{cur}>{label}</a>'
    nav = [link("/news/", "Latest", "latest")]
    if "opinion" in sections:
        nav.append(link("/news/opinion/", "Opinion", "opinion"))
    if "podcasts" in sections:
        nav.append(link("/news/podcasts/", "Podcasts", "podcasts"))
    nav.append(link("/news/about/", "About", "about"))
    nav.append(link("/news/ethics/", "Ethics", "ethics"))
    return f"""<header class="plate">
    <div class="plate-top">
      <a href="/">dankrecovery.com</a>
      <a class="plate-sub" href="#signup-title">Get the newsletter</a>
    </div>
    <a class="plate-name" href="/news/" aria-label="Dank Recovery News front page">
      <img class="seal" src="/logo.jpg" width="56" height="56" alt="">
      <span>Dank Recovery <b>News</b></span>
    </a>
    <nav class="sections" aria-label="Sections">
      {(chr(10) + '      ').join(nav)}
    </nav>
  </header>"""


def footer():
    year = dt.datetime.now(TZ).year
    return f"""<footer>
    <nav class="foot-links" aria-label="More">
      <a href="/news/">All news</a>
      <a href="/news/about/">About</a>
      <a href="/news/ethics/">Ethics &amp; corrections</a>
      <a href="/news/privacy/">Privacy</a>
      <a href="/news/feed.xml">RSS</a>
      <a href="https://www.facebook.com/DankRecovery">Facebook</a>
      <a href="https://twitter.com/dankrecovery">X</a>
      <a href="mailto:timothy@dankrecovery.com?subject=News%20tip">Send a tip</a>
    </nav>
    <p class="fine">&copy; {year} Dank Recovery LLC · St. Charles, Missouri</p>
  </footer>"""


SIGNUP = f"""<aside class="signup" aria-labelledby="signup-title">
      <h2 id="signup-title">Get the news by email</h2>
      <p>The week in recovery, sent to your inbox. No spam, and you can leave anytime.</p>
      <form id="signup" novalidate>
        <label class="hp" aria-hidden="true">Leave this empty <input type="text" name="_honey" tabindex="-1" autocomplete="off"></label>
        <input type="email" name="email" autocomplete="email" inputmode="email" placeholder="you@example.com" aria-label="Email" required>
        <button class="btn primary" type="submit">Sign up</button>
      </form>
      <p class="msg" id="signup-msg" role="status" hidden></p>
      <p class="tiny">See our <a href="/news/privacy/">privacy policy</a>.</p>
    </aside>
    <script>
    (function () {{
      var f = document.getElementById('signup'), msg = document.getElementById('signup-msg');
      if (!f) return;
      f.addEventListener('submit', function (ev) {{
        ev.preventDefault();
        var em = f.elements.email;
        if (!em.value.trim() || !em.checkValidity()) {{ msg.hidden = false; msg.textContent = 'Enter a valid email address.'; em.focus(); return; }}
        var b = new URLSearchParams();
        b.set('email', em.value.trim()); b.set('source', 'news'); b.set('_honey', f.elements._honey.value);
        f.querySelector('button').disabled = true;
        function done() {{ f.hidden = true; msg.hidden = false; msg.textContent = "You're on the list."; }}
        fetch('{SIGNUP_ENDPOINT}', {{ method: 'POST', mode: 'no-cors', body: b }}).then(done, done);
      }});
    }})();
    </script>"""

HEAD_COMMON = """<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="icon" href="/logo.jpg">
<link rel="alternate" type="application/rss+xml" title="Dank Recovery News" href="/news/feed.xml">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Alfa+Slab+One&family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/news/news.css">"""


def site_head(title, desc, url):
    return f"""{HEAD_COMMON}
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{url}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{PUBLICATION}">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{SITE}/news/card.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:site" content="{X_HANDLE}">
<meta name="twitter:image" content="{SITE}/news/card.png">"""


def kicker_html(s):
    cls = " flag" if s["type"] in ("opinion", "sponsored") else ""
    return f'<span class="kicker{cls}">{e(s["kicker"])}</span>'


def story_list(stories):
    items = "\n".join(
        f"""        <li><a href="/news/{s['slug']}/"><span class="meta">{kicker_html(s)}<span class="when">{nice_date(s['date_obj'])}</span></span>
          <span class="title">{e(s['title'])}</span><span class="sub">{e(s['dek'])}</span></a></li>"""
        for s in stories)
    return f'<ul class="stories">\n{items}\n      </ul>'


# ---------- pages ----------

def article_page(m, stories, sections):
    url, title, dek = m["url"], m["title"], m["dek"]
    card = f"{url}card.png"
    iso = m["iso"]
    is_staff = m["author"] == DEFAULT_AUTHOR
    author_ld = {"@type": "Person", "name": m["author"]}
    if is_staff:
        author_ld["url"] = AUTHOR_URL
    byline = f'<a href="/news/about/#timothy-kavanagh"><b>{e(m["author"])}</b></a>' if is_staff else f'<b>{e(m["author"])}</b>'
    x_share = f"https://twitter.com/intent/tweet?text={quote(title)}&url={quote(url)}&via=dankrecovery"
    fb_share = f"https://www.facebook.com/sharer/sharer.php?u={quote(url)}"
    ld = {
        "@context": "https://schema.org", "@type": TYPES[m["type"]][2],
        "headline": title, "description": dek, "image": [card],
        "datePublished": iso, "dateModified": m["modified_iso"] or iso,
        "articleSection": m["kicker"],
        "author": author_ld,
        "publisher": {"@type": "NewsMediaOrganization", "name": PUBLICATION, "url": f"{SITE}/news/",
                      "logo": {"@type": "ImageObject", "url": f"{SITE}/logo.jpg"},
                      "publishingPrinciples": f"{SITE}/news/ethics/"},
        "mainEntityOfPage": url,
    }
    mod_tag = f'\n<meta property="article:modified_time" content="{m["modified_iso"]}">' if m["modified_iso"] else ""
    updated = f'<p class="updated">{e(m["updated"])}</p>' if m.get("updated") else ""
    note = ""
    if m["type"] == "opinion":
        note = '<p class="updated">Opinion. This piece is the writer\'s view, not a news report.</p>'
    elif m["type"] == "sponsored":
        note = '<p class="updated">Sponsored content. This was paid for and is not a news report.</p>'
    sec = TYPES[m["type"]][1]
    current = sec if sec in sections else "latest"
    crumb = f'<a href="/news/{sec}/">{e(m["kicker"])}</a>' if sec else e(m["kicker"])
    author_box = f"""<div class="author-box">
      <p>{e(AUTHOR_BLURB)} <a href="/news/about/">About the newsroom</a> · <a href="mailto:timothy@dankrecovery.com?subject=Correction">Report an error</a></p>
    </div>""" if is_staff else ""
    others = [s for s in stories if s["slug"] != m["slug"]][:3]
    more = f"""<section class="more" aria-label="More stories">
      <h2 class="rail-title">More from Dank Recovery News</h2>
      {story_list(others)}
    </section>""" if others else ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
{HEAD_COMMON}
<title>{e(title)} | Dank Recovery News</title>
<meta name="description" content="{e(dek)}">
<meta name="author" content="{e(m['author'])}">
<link rel="canonical" href="{url}">
<meta property="og:type" content="article">
<meta property="og:site_name" content="{PUBLICATION}">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(dek)}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{card}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="{e(title)}">
<meta property="article:published_time" content="{iso}">{mod_tag}
<meta property="article:author" content="{e(m['author'])}">
<meta property="article:section" content="{e(m['kicker'])}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:site" content="{X_HANDLE}">
<meta name="twitter:title" content="{e(title)}">
<meta name="twitter:description" content="{e(dek)}">
<meta name="twitter:image" content="{card}">
<script type="application/ld+json">{json.dumps(ld)}</script>
</head>
<body>
<div class="wrap">
  {header(current, sections)}
  <main class="col">
    <article class="story">
      <p class="label{' flag' if m['type'] in ('opinion', 'sponsored') else ''}">{crumb}</p>
      <h1>{e(title)}</h1>
      <p class="dek">{e(dek)}</p>
      <p class="byline"><span>By {byline}</span><time datetime="{iso}">{nice_when(m)}</time></p>
      {note}
      {updated}
      <div class="story-body">
{m['body_html']}
      </div>
      {author_box}
    </article>
    <div class="share" aria-label="Share this story">
      <a class="btn" href="{e(x_share)}" target="_blank" rel="noopener">Post on X</a>
      <a class="btn" href="{e(fb_share)}" target="_blank" rel="noopener">Share on Facebook</a>
      <button class="btn" type="button" id="copy">Copy link</button>
    </div>
    <script>
    document.getElementById('copy').addEventListener('click', function () {{
      var b = this, u = '{url}';
      function ok() {{ b.textContent = 'Copied'; }}
      if (navigator.clipboard) navigator.clipboard.writeText(u).then(ok, function () {{ prompt('Copy this link:', u); }});
      else prompt('Copy this link:', u);
    }});
    </script>
    {SIGNUP}
    {more}
  </main>
  {footer()}
</div>
</body>
</html>
"""


def front_page(stories, sections, section=None):
    """The news front page, or one section's page when `section` is given."""
    if section:
        label = next(v[0] for v in TYPES.values() if v[1] == section)
        title, desc, url = f"{label} | {PUBLICATION}", SECTION_BLURB[section], f"{SITE}/news/{section}/"
        heading = f'<div class="section-head"><h1>{label}</h1><p>{e(desc)}</p></div>'
        current = section
    else:
        title, desc, url, heading, current = PUBLICATION, TAGLINE, f"{SITE}/news/", f'<h1 class="vh">{PUBLICATION}</h1>', "latest"
    if stories:
        lead, rest = stories[0], stories[1:]
        body = f"""<a class="lead" href="/news/{lead['slug']}/">
        <span class="meta">{kicker_html(lead)}<span class="when">{nice_date(lead['date_obj'])}</span></span>
        <span class="lead-title">{e(lead['title'])}</span>
        <span class="lead-dek">{e(lead['dek'])}</span>
        <span class="lead-by">By {e(lead['author'])}</span>
      </a>"""
        if rest:
            body += f'\n      <h2 class="rail-title">Latest</h2>\n      {story_list(rest)}'
    else:
        body = '<p class="empty">First stories coming soon.</p>'
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
{site_head(title, desc, url)}
</head>
<body>
<div class="wrap">
  {header(current, sections)}
  <main class="front">
    <section class="front-main" aria-label="Latest stories">
      {heading}
      {body}
    </section>
    <div class="rail">
      {SIGNUP}
      <div class="rail-box">
        <h2 class="rail-title">About this newsroom</h2>
        <p>{e(TAGLINE)} Reported and edited by Timothy Kavanagh.</p>
        <p><a href="/news/about/">Who we are</a> · <a href="/news/ethics/">Our standards</a></p>
      </div>
      <div class="rail-box">
        <h2 class="rail-title">Got a tip?</h2>
        <p>Know something we should cover? <a href="mailto:timothy@dankrecovery.com?subject=News%20tip">Email the newsroom</a>.</p>
      </div>
    </div>
  </main>
  {footer()}
</div>
</body>
</html>
"""


def static_page(path, sections):
    """About, Ethics, Privacy: built from news-src/pages/<slug>.md."""
    meta, body = split_header(path)
    for k in ("title", "description"):
        if not meta.get(k):
            sys.exit(f"pages/{path.name}: needs a '{k}:' line")
    slug = path.stem
    url = f"{SITE}/news/{slug}/"
    extra = ""
    if slug == "about":
        ld = {"@context": "https://schema.org", "@type": "NewsMediaOrganization",
              "name": PUBLICATION, "url": f"{SITE}/news/", "logo": f"{SITE}/logo.jpg",
              "email": "timothy@dankrecovery.com",
              "publishingPrinciples": f"{SITE}/news/ethics/", "correctionsPolicy": f"{SITE}/news/ethics/",
              "parentOrganization": {"@type": "Organization", "name": "Dank Recovery LLC", "url": f"{SITE}/"},
              "founder": {"@type": "Person", "name": DEFAULT_AUTHOR, "url": AUTHOR_URL},
              "sameAs": ["https://www.facebook.com/DankRecovery", "https://twitter.com/dankrecovery"]}
        extra = f'\n<script type="application/ld+json">{json.dumps(ld)}</script>'
    return slug, f"""<!DOCTYPE html>
<html lang="en">
<head>
{site_head(meta['title'] + ' | ' + PUBLICATION, meta['description'], url)}{extra}
</head>
<body>
<div class="wrap">
  {header(slug, sections)}
  <main class="col page">
    <h1>{e(meta['title'])}</h1>
{md(body)}
  </main>
  {footer()}
</div>
</body>
</html>
"""


def feed(stories):
    items = []
    for s in stories[:30]:
        pub = format_datetime(s["dt"] or dt.datetime.combine(s["date_obj"], dt.time(12), dt.timezone.utc))
        items.append(f"""  <item>
    <title>{e(s['title'])}</title>
    <link>{s['url']}</link>
    <guid>{s['url']}</guid>
    <pubDate>{pub}</pubDate>
    <category>{e(s['kicker'])}</category>
    <description>{e(s['dek'])}</description>
  </item>""")
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
  <title>Dank Recovery News</title>
  <link>{SITE}/news/</link>
  <description>{e(TAGLINE)}</description>
  <language>en-us</language>
{chr(10).join(items)}
</channel>
</rss>
"""


def sitemap(stories, page_slugs, sections):
    """Every page on the site, for regular Google Search."""
    pages = [(f"{SITE}/", None), (f"{SITE}/news/", stories[0]["iso"] if stories else None)]
    pages += [(f"{SITE}/news/{s}/", None) for s in sorted(sections) + sorted(page_slugs)]
    pages += [(s["url"], s["modified_iso"] or s["iso"]) for s in stories]
    rows = []
    for loc, mod in pages:
        lastmod = f"<lastmod>{mod}</lastmod>" if mod else ""
        rows.append(f"  <url><loc>{loc}</loc>{lastmod}</url>")
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{chr(10).join(rows)}
</urlset>
"""


def news_sitemap(stories, today=None):
    """Google News sitemap: stories from the last NEWS_SITEMAP_DAYS days. Sponsored pieces stay out."""
    today = today or dt.datetime.now(TZ).date()
    cutoff = today - dt.timedelta(days=NEWS_SITEMAP_DAYS)
    rows = []
    for s in stories:
        if s["type"] == "sponsored" or not (cutoff <= s["date_obj"] <= today):
            continue
        rows.append(f"""  <url>
    <loc>{s['url']}</loc>
    <news:news>
      <news:publication>
        <news:name>{e(PUBLICATION)}</news:name>
        <news:language>en</news:language>
      </news:publication>
      <news:publication_date>{s['iso']}</news:publication_date>
      <news:title>{e(s['title'])}</news:title>
    </news:news>
  </url>""")
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
        xmlns:news="http://www.google.com/schemas/sitemap-news/0.9">
{chr(10).join(rows)}
</urlset>
""", len(rows)


def main():
    stories = [parse(p) for p in sorted(SRC.glob("*.md")) if not p.name.startswith("_")]
    stories.sort(key=lambda s: (s["date_obj"], s.get("time") or ""), reverse=True)
    page_files = [p for p in sorted(PAGES.glob("*.md")) if not p.name.startswith("_")]
    reserved = {p.stem for p in page_files} | set(SECTION_BLURB)
    for s in stories:
        if s["slug"] in reserved:
            sys.exit(f"{s['slug']}.md: that name is taken by a section or page, rename the file")
    by_section = {sec: [s for s in stories if TYPES[s["type"]][1] == sec] for sec in SECTION_BLURB}
    sections = {sec for sec, lst in by_section.items() if lst}

    for s in stories:
        d = OUT / s["slug"]
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(article_page(s, stories, sections), encoding="utf-8")
        make_card(s, d / "card.png")
        print("built", f"news/{s['slug']}/")
    for sec in sections:
        d = OUT / sec
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(front_page(by_section[sec], sections, sec), encoding="utf-8")
    for p in page_files:
        slug, page = static_page(p, sections)
        d = OUT / slug
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(page, encoding="utf-8")
    make_card({"title": "Recovery news and what's happening in the fellowship worldwide"}, OUT / "card.png")
    (OUT / "index.html").write_text(front_page(stories, sections), encoding="utf-8")
    (OUT / "feed.xml").write_text(feed(stories), encoding="utf-8")
    (ROOT / "sitemap.xml").write_text(sitemap(stories, [p.stem for p in page_files], sections), encoding="utf-8")
    ns, fresh = news_sitemap(stories)
    (ROOT / "news-sitemap.xml").write_text(ns, encoding="utf-8")
    print(f"front page, {len(page_files)} pages, feed, sitemaps: {len(stories)} stories, {fresh} in the Google News sitemap")


if __name__ == "__main__":
    main()
