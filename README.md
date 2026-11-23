# dankrecovery

Source for dankrecovery.com (GitHub Pages).

- `index.html`: homepage
- `shop/index.html`: forwards dankrecovery.com/shop to the Fourthwall store
- `CNAME`: custom domain for GitHub Pages

## Dank Recovery News

Stories live in `news-src/<slug>.md` (title, dek, date, author header, then Markdown).
Run `python3 tools/build_news.py` to build each article page, its share card for X and Facebook,
the `/news/` front page, `feed.xml`, `sitemap.xml` and `news-sitemap.xml` (the one Google News reads;
it only lists stories from the last 2 days, so rebuild whenever you publish). Needs `pip install markdown pillow`.
Name a file `_something.md` to keep it as a draft.

Add `type: opinion`, `type: podcast` or `type: sponsored` to a story's header to label it; leave it off for regular news.
The About, Ethics and Privacy pages are plain text files in `news-src/pages/`.
