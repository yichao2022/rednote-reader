#!/usr/bin/env python3
"""
Search rednote.com for notes matching a query.
Returns structured results that can be used with reader/images/video modules.

Usage:
  python -m src.search "穿搭"
  python -m src.search "武康路 街拍" --max 20
"""

import argparse, json, os, sys, time
from pathlib import Path

DEFAULT_SESSION = os.environ.get(
    "REDNOTE_SESSION",
    str(Path.home() / ".config" / "rednote" / "session.json")
)

from playwright.sync_api import sync_playwright


def search(query: str, max_results: int = 10,
           session_file: str | None = None) -> list[dict]:
    """
    Search rednote.com for notes.

    Returns list of dicts with keys:
      note_id: str
      title: str
      author: str
      url: str (full rednote.com URL)
    """
    session_file = session_file or DEFAULT_SESSION
    storage = Path(session_file)
    if not storage.exists():
        print(f"ERROR: Session file not found: {session_file}")
        return []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            storage_state=str(storage),
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/134.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1440, "height": 900},
        )
        page = ctx.new_page()

        url = (f"https://www.rednote.com/search_result"
               f"?keyword={query}&source=web_search_result_notes")
        page.goto(url, timeout=30000)
        page.wait_for_load_state("networkidle", timeout=20000)
        time.sleep(4)

        # Extract note-item cards
        items = page.eval_on_selector_all("section.note-item", """
            els => els.map(el => {
                const a = el.querySelector('a[href*="explore"]');
                const href = a ? a.getAttribute('href') : '';
                const text = el.textContent || '';
                // Extract images from the card
                const imgs = Array.from(el.querySelectorAll('img'));
                const imgSrcs = imgs.map(img => img.getAttribute('src')).filter(Boolean);

                return {
                    href: href,
                    full_text: text.slice(0, 300),
                    images: imgSrcs.slice(0, 2),
                };
            }).filter(e => e.href)
        """)

        results = []
        for item in items:
            note_id = ""
            if "/explore/" in item["href"]:
                note_id = item["href"].split("/explore/")[1].split("?")[0].split("#")[0]

            lines = [l.strip() for l in item["full_text"].split("\n") if l.strip()]
            author = lines[0] if lines else ""
            title = lines[1] if len(lines) > 1 else ""

            results.append({
                "note_id": note_id,
                "title": title[:120],
                "author": author[:80],
                "url": f"https://www.rednote.com/explore/{note_id}" if note_id else "",
                "cover_images": item["images"],
            })

        browser.close()

    return results[:max_results]


def main():
    parser = argparse.ArgumentParser(description="Search rednote.com")
    parser.add_argument("query", help="Search query")
    parser.add_argument("--max", type=int, default=10,
                        help="Max results (default 10)")
    args = parser.parse_args()

    results = search(args.query, max_results=args.max)
    print(f"SEARCH: '{args.query}' — {len(results)} results\n")
    for r in results:
        print(f"  [{r['note_id']}] {r['title'][:60]}")
        if r["author"]:
            print(f"       {r['author'][:40]}")
        print(f"       {r['url']}")
        if r["cover_images"]:
            print(f"       cover: {r['cover_images'][0][:100]}")
        print()


if __name__ == "__main__":
    main()
