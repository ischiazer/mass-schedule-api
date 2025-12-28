#!/usr/bin/env python3
"""
Small utility to fetch the full HTML of https://www.legrandaction.com/

Provides two modes:
- static: use requests to fetch the server-rendered HTML
- rendered: use Playwright to run a headless browser and return the JS-rendered HTML

You can import the functions or run this file as a CLI.

Requirements: `requests`, `playwright` (both are listed in the repository's requirements.txt)

Example (sync):
    html = fetch_static_html('https://www.legrandaction.com/')

Example (rendered):
    html = get_rendered_html('https://www.legrandaction.com/')

"""
from __future__ import annotations

import argparse
import asyncio
import sys
from typing import Optional

import requests


def fetch_static_html(url: str, timeout: int = 15) -> str:
    """Fetch HTML using a simple HTTP GET request.

    Args:
        url: The page URL.
        timeout: seconds for requests timeout.

    Returns:
        The raw HTML as returned by the server (str).

    Raises:
        requests.HTTPError on non-2xx responses.
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0 Safari/537.36"
        )
    }
    resp = requests.get(url, headers=headers, timeout=timeout)
    resp.raise_for_status()
    return resp.text


async def _fetch_rendered_html_async(url: str, timeout: int = 30, wait_until: Optional[str] = "networkidle") -> str:
    """Use Playwright to fetch the fully rendered HTML.

    Args:
        url: The page URL.
        timeout: navigation timeout in seconds.
        wait_until: Playwright wait_until value (e.g., 'load', 'domcontentloaded', 'networkidle').

    Returns:
        The HTML content after rendering.

    Raises:
        RuntimeError if Playwright isn't available or an error occurs.
    """
    try:
        from playwright.async_api import async_playwright
    except Exception as e:  # pragma: no cover - runtime environment
        raise RuntimeError("Playwright is not installed or failed to import") from e

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        try:
            context = await browser.new_context()
            page = await context.new_page()
            # convert to ms for Playwright
            await page.goto(url, timeout=timeout * 1000, wait_until=wait_until)
            # ensure network is idle/complete
            try:
                await page.wait_for_load_state(wait_until, timeout=5_000)
            except Exception:
                # non-fatal; continue to grab content
                pass
            content = await page.content()
            return content
        finally:
            await browser.close()


def get_rendered_html(url: str, timeout: int = 30, wait_until: Optional[str] = "networkidle") -> str:
    """Sync wrapper around the Playwright async renderer.

    This runs an asyncio event loop under the hood.
    """
    return asyncio.run(_fetch_rendered_html_async(url, timeout=timeout, wait_until=wait_until))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch full HTML from a URL (static or JS-rendered).")
    parser.add_argument("url", nargs="?", default="https://www.legrandaction.com/", help="URL to fetch")
    parser.add_argument("--rendered", action="store_true", help="Use Playwright to fetch JS-rendered HTML")
    parser.add_argument("--out", "-o", help="Write output HTML to a file (otherwise prints to stdout)")
    parser.add_argument("--timeout", type=int, default=30, help="Timeout in seconds for navigation or request")
    args = parser.parse_args(argv)

    try:
        if args.rendered:
            html = get_rendered_html(args.url, timeout=args.timeout)
        else:
            html = fetch_static_html(args.url, timeout=args.timeout)
    except Exception as exc:
        print(f"Error fetching {args.url}: {exc}", file=sys.stderr)
        return 2

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"Saved HTML to {args.out}")
    else:
        # Print to stdout so the caller can pipe or capture it
        sys.stdout.write(html)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
