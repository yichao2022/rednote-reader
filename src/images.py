#!/usr/bin/env python3
"""
Extract images from a rednote.com note using headless Playwright.
Images are stored at sns-web-i10.rednotecdn.com and rendered via Swiper.

Usage:
  python -m src.images --note-id <id> --xsec-token <token>
  python -m src.images --url "https://www.rednote.com/explore/..."
"""

import argparse, json, os, sys, time, urllib.request, urllib.error
from pathlib import Path
from urllib.parse import urlparse

DEFAULT_SESSION = os.environ.get(
    "REDNOTE_SESSION",
    str(Path.home() / ".config" / "rednote" / "session.json")
)
OUTPUT_DIR = Path("/tmp/rednote_images")

from playwright.sync_api import sync_playwright


def extract_images(note_id: str, xsec_token: str | None = None,
                   url: str | None = None,
                   max_images: int = 9,
                   download: bool = False,
                   output_dir: str | None = None,
                   session_file: str | None = None) -> list[dict]:
    """
    Extract image URLs from a rednote note.
    
    Returns list of dicts: [{"index": 1, "url": "...", "local_path": "..."}]
    If download=False, local_path is None.
    """
    session_file = session_file or DEFAULT_SESSION
    storage = Path(session_file)
    if not storage.exists():
        print(f"ERROR: Session file not found: {session_file}")
        return []

    out = Path(output_dir) if output_dir else OUTPUT_DIR
    out.mkdir(parents=True, exist_ok=True)

    base_url = url or f"https://www.rednote.com/explore/{note_id}?xsec_token={xsec_token}"

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

        page.goto(base_url, timeout=30000)
        page.wait_for_load_state("networkidle", timeout=20000)
        time.sleep(4)

        # Extract images from Swiper slides
        urls = page.eval_on_selector_all(
            "div.swiper-slide img, div.note-slider-img img",
            "els => els.map(el => el.getAttribute('src')).filter(Boolean)"
        )

        browser.close()

    # Deduplicate by base URL (stripping query params)
    seen = set()
    unique = []
    for u in urls:
        base = u.split("?")[0] if "?" in u else u
        # Also strip transformation params
        base = base.split("!")[0] if "!" in base else base
        if base not in seen:
            seen.add(base)
            unique.append(u)

    # Filter to note images only (not avatars, logos)
    note_imgs = [u for u in unique if "notes_pre_post" in u or "rednotecdn" in u]
    if note_imgs:
        unique = note_imgs

    # Limit
    unique = unique[:max_images]

    result = []
    for i, img_url in enumerate(unique):
        entry = {"index": i + 1, "url": img_url, "local_path": None}
        if download:
            try:
                ext = img_url.split("?")[0].split(".")[-1][:4]
                if ext not in ("jpg", "jpeg", "png", "webp"):
                    ext = "jpg"
                path = out / f"img_{i+1:02d}.{ext}"
                urllib.request.urlretrieve(img_url, path)
                entry["local_path"] = str(path)
            except Exception as e:
                print(f"Download failed [{i+1}]: {e}", flush=True)
        result.append(entry)

    return result


def main():
    parser = argparse.ArgumentParser(description="Extract images from a rednote note")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--note-id")
    group.add_argument("--url")
    parser.add_argument("--xsec-token")
    parser.add_argument("--max-images", type=int, default=9)
    parser.add_argument("--download", action="store_true",
                        help="Download images to /tmp/rednote_images")
    args = parser.parse_args()

    if args.url:
        images = extract_images("", url=args.url,
                                max_images=args.max_images, download=args.download)
    elif not args.xsec_token:
        print("ERROR: --xsec-token required with --note-id")
        sys.exit(1)
    else:
        images = extract_images(args.note_id, args.xsec_token,
                                max_images=args.max_images, download=args.download)

    print(f"IMAGES: {len(images)}")
    for img in images:
        print(f"  [{img['index']}] {img['url'][:120]}")
        if img["local_path"]:
            print(f"       saved: {img['local_path']}")


if __name__ == "__main__":
    main()
