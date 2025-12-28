# Fetching legrandaction.com HTML

This project provides `fetch_legrandaction.py`, a small utility to fetch the full HTML for
https://www.legrandaction.com/.

Usage
-----

1) Static fetch (fast, server-rendered HTML):

```sh
python fetch_legrandaction.py https://www.legrandaction.com/ -o legrand_static.html
```

2) Rendered fetch (runs a headless browser via Playwright to execute JS and return the post-render HTML):

```sh
python fetch_legrandaction.py --rendered https://www.legrandaction.com/ -o legrand_rendered.html
```

Notes
-----
- Playwright must be installed and the browsers must be installed (if not already). To install Playwright browsers:

```sh
python -m pip install playwright
python -m playwright install
```

- The rendered mode is slower but required if the page content is produced via client-side JavaScript.

- The script prints HTML to stdout by default so you can pipe it directly into other tools.

Example: pipe to a file and then call your OpenAI upload step

```sh
python fetch_legrandaction.py --rendered https://www.legrandaction.com/ > full_page.html
# then POST or send the contents to OpenAI as you normally would
```
