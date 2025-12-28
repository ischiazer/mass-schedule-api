#!/usr/bin/env python3
import sys
import json
import urllib.parse

from playwright.sync_api import sync_playwright

if len(sys.argv) < 2:
    print("Usage: inspect_google.py <cinema> [location]")
    sys.exit(2)

cinema = sys.argv[1]
location = sys.argv[2] if len(sys.argv) > 2 else ''
query = f"showtimes {cinema} {location}".strip()
url = "https://www.google.com/search?q=" + urllib.parse.quote(query) + "&hl=en"

with sync_playwright() as pw:
  # Use a desktop-like UA and viewport to reduce bot-detection and increase chance of
  # Google returning the showtimes card.
  browser = pw.chromium.launch(headless=False)
  context = browser.new_context(
    user_agent=(
      "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/120.0 Safari/537.36"
    ),
    viewport={"width": 1366, "height": 768},
    locale="en-US",
  )
  page = context.new_page()
  page.goto(url, timeout=45000, wait_until='networkidle')
  # allow extra time for dynamic content
  page.wait_for_timeout(2500)

  js = r"""
(function(){
  const timeRegex = /\b\d{1,2}[:h]\d{2}\b/g;
  const candidates = {};
  const nodes = Array.from(document.querySelectorAll('body *'));
  function pathFor(el){
    const parts = [];
    let cur = el;
    for(let i=0;i<6 && cur;i++){
      let part = cur.tagName.toLowerCase();
      if(cur.className && typeof cur.className==='string'){
        const cls = cur.className.trim().split(/\s+/).slice(0,2).join('.');
        if(cls) part += '.'+cls;
      }
      parts.unshift(part);
      cur = cur.parentElement;
    }
    return parts.join(' > ');
  }
  for(const n of nodes){
    const txt = (n.innerText||'').trim();
    if(!txt) continue;
    if(timeRegex.test(txt)){
      const p = pathFor(n);
      if(!candidates[p]) candidates[p] = (txt.length>200?txt.slice(0,200)+"...":txt);
    }
  }
  return candidates;
})();
"""
  candidates = page.evaluate(js)
  try:
    html = page.content()
    with open('google_showtimes_inspect.html', 'w', encoding='utf-8') as f:
      f.write(html)
  except Exception:
    pass
  print(json.dumps(candidates, ensure_ascii=False, indent=2))
  browser.close()
