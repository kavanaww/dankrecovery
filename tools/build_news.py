#!/usr/bin/env python3
"""Build Dank Recovery News.

Write each story as news-src/<slug>.md:

    ---
    title: Headline goes here
    dek: One-sentence summary shown under the headline and in share previews.
    date: 2026-11-22
    author: Timothy Kavanagh
    updated: optional note shown at the top, e.g. a correction
    ---
    Story body in Markdown.

Then run:  python3 tools/build_news.py

It writes, for every story:
  news/<slug>/index.html   the article page, with X and Facebook share tags
  news/<slug>/card.png     the 1200x630 image X and Facebook show in the preview
and rebuilds news/index.html (newest first) and news/feed.xml (RSS).
Files whose name starts with "_" are skipped (drafts).
"""
import datetime as dt
import html
import json
import re
import sys
from email.utils import format_datetime
from pathlib import Path

import markdown
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "news-src"
OUT = ROOT / "news"
FONTS = Path(__file__).resolve().parent / "fonts"
SITE = "https://dankrecovery.com"
X_HANDLE = "@dankrecovery"
DEFAULT_AUTHOR = "Moose Kavanagh"
SIGNUP_ENDPOINT = "https://script.google.com/macros/s/AKfycbyEt3vbVzJD7ltwRnEnwiYEEIGz453PrwWQ8f9dHvfg3XHEx8GCQePpcfzzDBb7BaFuDw/exec"

INK, BONE, ASH, RULE, BRASS = "#0d0c0b", "#ece4d2", "#a39c8c", "#37322b", "#c9a24a"

e = html.escape


def parse(path):
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", text, re.S)
    if not m:
        sys.exit(f"{path.name}: missing the --- header block at the top")
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip().lower()] = v.strip()
    for k in ("title", "dek", "date"):
        if not meta.get(k):
            sys.exit(f"{path.name}: needs a '{k}:' line")
    try:
        meta["date_obj"] = dt.date.fromisoformat(meta["date"])
    except ValueError:
        sys.exit(f"{path.name}: date must look like 2026-11-22")
    meta["slug"] = path.stem
    meta["author"] = meta.get("author") or DEFAULT_AUTHOR
    meta["body_html"] = markdown.markdown(m.group(2), extensions=["extra", "smarty"])
    meta["url"] = f"{SITE}/news/{meta['slug']}/"
    return meta


def nice_date(d):
    return d.strftime("%B %-d, %Y")


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
    d.text((PAD, PAD - 6), "DANK RECOVERY NEWS", font=mono, fill=BRASS)
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


# ---------- pages ----------

def header(current):
    def link(href, label, key):
        cur = ' aria-current="page"' if key == current else ""
        return f'<a href="{href}"{cur}>{label}</a>'
    return f"""<header class="top">
    <a class="brand" href="/" aria-label="Dank Recovery home">
      <img class="seal" src="/logo.jpg" width="52" height="52" alt="Dank Recovery seal">
      <span><span class="brand-name">DANK RECOVERY</span><br><span class="brand-est">NEWS</span></span>
    </a>
    <nav class="top-nav" aria-label="Sections">
      {link('/news/', 'News', 'news')}
      <a href="https://shop.dankrecovery.com/">Shop</a>
      <a href="/#podcast">Podcast</a>
    </nav>
  </header>"""


FOOTER = """<footer>
    <nav class="foot-links" aria-label="More">
      <a href="/news/">All news</a>
      <a href="/news/ethics/">Ethics &amp; corrections</a>
      <a href="/news/feed.xml">RSS</a>
      <a href="https://www.facebook.com/DankRecovery">Facebook</a>
      <a href="https://twitter.com/dankrecovery">X</a>
      <a href="mailto:timothy@dankrecovery.com?subject=News%20tip">Send a tip</a>
    </nav>
    <p class="fine">Dank Recovery News · Dank Recovery LLC · St. Charles, Missouri</p>
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


def article_page(m):
    from urllib.parse import quote
    url, title, dek = m["url"], m["title"], m["dek"]
    card = f"{url}card.png"
    iso = m["date_obj"].isoformat()
    x_share = f"https://twitter.com/intent/tweet?text={quote(title)}&url={quote(url)}&via=dankrecovery"
    fb_share = f"https://www.facebook.com/sharer/sharer.php?u={quote(url)}"
    ld = {
        "@context": "https://schema.org", "@type": "NewsArticle",
        "headline": title, "description": dek, "image": [card],
        "datePublished": iso, "author": {"@type": "Person", "name": m["author"]},
        "publisher": {"@type": "Organization", "name": "Dank Recovery News",
                      "logo": {"@type": "ImageObject", "url": f"{SITE}/logo.jpg"}},
        "mainEntityOfPage": url,
    }
    updated = f'<p class="updated">{e(m["updated"])}</p>' if m.get("updated") else ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
{HEAD_COMMON}
<title>{e(title)} | Dank Recovery News</title>
<meta name="description" content="{e(dek)}">
<meta name="author" content="{e(m['author'])}">
<link rel="canonical" href="{url}">
<meta property="og:type" content="article">
<meta property="og:site_name" content="Dank Recovery News">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(dek)}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{card}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="{e(title)}">
<meta property="article:published_time" content="{iso}">
<meta property="article:author" content="{e(m['author'])}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:site" content="{X_HANDLE}">
<meta name="twitter:title" content="{e(title)}">
<meta name="twitter:description" content="{e(dek)}">
<meta name="twitter:image" content="{card}">
<script type="application/ld+json">{json.dumps(ld)}</script>
</head>
<body>
<div class="wrap">
  {header('news')}
  <main>
    <article class="story">
      <p class="label"><a href="/news/">Dank Recovery News</a>{' · ' + e(m['label']) if m.get('label') else ''}</p>
      <h1>{e(title)}</h1>
      <p class="dek">{e(dek)}</p>
      <p class="byline"><span>By <b>{e(m['author'])}</b></span><time datetime="{iso}">{nice_date(m['date_obj'])}</time></p>
      {updated}
      <div class="story-body">
{m['body_html']}
      </div>
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
  </main>
  {FOOTER}
</div>
</body>
</html>
"""


def index_page(stories):
    if stories:
        items = "\n".join(
            f"""        <li><a href="/news/{s['slug']}/"><span class="when">{nice_date(s['date_obj'])}</span>
          <span class="title">{e(s['title'])}</span><span class="sub">{e(s['dek'])}</span></a></li>"""
            for s in stories)
        body = f'<ul class="stories">\n{items}\n      </ul>'
    else:
        body = '<p class="empty">First stories coming soon.</p>'
    desc = "Recovery news and trends, and what's happening in the fellowship worldwide."
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
{HEAD_COMMON}
<title>Dank Recovery News</title>
<meta name="description" content="{desc}">
<link rel="canonical" href="{SITE}/news/">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Dank Recovery News">
<meta property="og:title" content="Dank Recovery News">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="{SITE}/news/">
<meta property="og:image" content="{SITE}/news/card.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:site" content="{X_HANDLE}">
<meta name="twitter:image" content="{SITE}/news/card.png">
</head>
<body>
<div class="wrap">
  {header('news')}
  <main>
    <div class="masthead">
      <p class="label">Est. 2015</p>
      <h1>Dank Recovery News</h1>
      <p>{desc}</p>
    </div>
    <section aria-label="Latest stories">
      {body}
    </section>
    {SIGNUP}
  </main>
  {FOOTER}
</div>
</body>
</html>
"""


def feed(stories):
    items = []
    for s in stories[:30]:
        pub = format_datetime(dt.datetime.combine(s["date_obj"], dt.time(12), dt.timezone.utc))
        items.append(f"""  <item>
    <title>{e(s['title'])}</title>
    <link>{s['url']}</link>
    <guid>{s['url']}</guid>
    <pubDate>{pub}</pubDate>
    <description>{e(s['dek'])}</description>
  </item>""")
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
  <title>Dank Recovery News</title>
  <link>{SITE}/news/</link>
  <description>Recovery news and trends, and what's happening in the fellowship worldwide.</description>
  <language>en-us</language>
{chr(10).join(items)}
</channel>
</rss>
"""


def main():
    stories = [parse(p) for p in sorted(SRC.glob("*.md")) if not p.name.startswith("_")]
    stories.sort(key=lambda s: s["date_obj"], reverse=True)
    for s in stories:
        d = OUT / s["slug"]
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(article_page(s), encoding="utf-8")
        make_card(s, d / "card.png")
        print("built", f"news/{s['slug']}/")
    make_card({"title": "Recovery news and what's happening in the fellowship worldwide"}, OUT / "card.png")
    (OUT / "index.html").write_text(index_page(stories), encoding="utf-8")
    (OUT / "feed.xml").write_text(feed(stories), encoding="utf-8")
    print(f"index + feed: {len(stories)} stories")


if __name__ == "__main__":
    main()
