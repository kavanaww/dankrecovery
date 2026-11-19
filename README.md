# dankrecovery

Source for dankrecovery.com (GitHub Pages).

- `index.html`: homepage
- `shop/index.html`: forwards dankrecovery.com/shop to the Fourthwall store
- `CNAME`: custom domain for GitHub Pages

## Dank Recovery News

Stories live in `news-src/<slug>.md` (title, dek, date, author header, then Markdown).
Run `python3 tools/build_news.py` to build each article page, its share card for X and Facebook,
the `/news/` front page and `feed.xml`. Needs `pip install markdown pillow`.
Name a file `_something.md` to keep it as a draft.
