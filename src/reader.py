#!/usr/bin/env python3
"""
Read text content from a rednote.com note using headless Playwright.

Usage:
  python -m src.reader --note-id <id> --xsec-token <token>
  python -m src.reader --url "https://www.rednote.com/explore/<id>?xsec_token=<token>"
"""

import argparse, json, os, sys, time
from pathlib import Path

DEFAULT_SESSION = os.environ.get(
    "REDNOTE_SESSION",
    str(Path.home() / ".config" / "rednote" / "session.json")
)

from playwright.sync_api import sync_playwright

from .urls import looks_like_login_wall, normalize_note_url


def _load_session(session_file: str) -> dict | None:
    path = Path(session_file)
    if not path.exists():
        print(f"ERROR: Session file not found: {session_file}")
        print("Run `python -m src.login` first to create one.")
        return None
    with open(path) as f:
        data = json.load(f)
    cookies = data.get("cookies", [])
    a1 = next((c for c in cookies if c.get("name") == "a1"), None)
    if not a1 or not a1.get("value"):
        print("ERROR: Session expired. Re-run `python -m src.login`.")
        return None
    return data


def read_note(note_id: str, xsec_token: str | None = None,
              url: str | None = None,
              session_file: str | None = None) -> dict:
    """
    Read a rednote note's text content.
    
    Returns dict with keys: title, content, comments, hashtags.
    """
    session_file = session_file or DEFAULT_SESSION
    storage = _load_session(session_file)
    if not storage:
        return {"error": "no valid session"}

    try:
        base_url = normalize_note_url(url=url, note_id=note_id, xsec_token=xsec_token)
    except ValueError as e:
        return {"error": str(e)}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            storage_state=str(Path(session_file)),
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/134.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1440, "height": 900},
        )
        page = ctx.new_page()

        page.goto(base_url, timeout=30000, wait_until="domcontentloaded")
        # Wait for main content (faster than networkidle + sleep)
        try:
            page.wait_for_selector('.note-content, .desc, .title', timeout=5000)
        except:
            pass  # Continue even if selector not found

        title = page.title()
        body = page.inner_text("body")
        final_url = page.url

        browser.close()

    if looks_like_login_wall(title, body):
        return {
            "error": (
                "login wall detected — session may be expired, or the URL was still "
                f"on xiaohongshu.com. Tried: {base_url} (final: {final_url}). "
                "Re-run `python -m src.login`, or pass --note-id + --xsec-token."
            )
        }

    # Parse content
    lines = [l.strip() for l in body.split("\n")
             if l.strip() and len(l.strip()) > 15]

    skip_phrases = [
        "Log in to get notes", "Scan QR code", "How to scan",
        "Log in with phone number", "New users can log in directly",
        "Agree and continue", "Cancel", "Terms of Service",
        "Privacy Policy", "Log in to get started",
        "Discover content", "Search for the latest",
        "View saved and liked", "Connect and engage",
        "Read and agree", "Children and Teenagers",
        "Reminder", "It looks like you're using",
        "Sign in with Google", "Sign in with Apple",
        "Hover to see their info",
    ]
    clean_lines = [
        l for l in lines
        if not any(p in l for p in skip_phrases)
    ]

    # Separate hashtags from running text
    hashtags = [l for l in clean_lines if l.startswith("#")]
    content = [l for l in clean_lines if not l.startswith("#")]

    # Find where comments start
    comment_idx = len(content)
    for i, line in enumerate(content):
        if any(kw in line for kw in ["评论", "Comment", "全部评论"]):
            comment_idx = i
            break
    note_body = content[:comment_idx]
    comments = content[comment_idx:]

    result = {
        "title": title.replace(" - rednote", ""),
        "content": note_body,
        "comments": [c for c in comments if len(c) > 20],
        "hashtags": hashtags,
    }
    return result


def main():
    parser = argparse.ArgumentParser(description="Read a rednote note")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--note-id")
    group.add_argument("--url")
    parser.add_argument("--xsec-token")
    args = parser.parse_args()

    if args.url:
        result = read_note(note_id="", url=args.url)
    elif not args.xsec_token:
        print("ERROR: --xsec-token required with --note-id")
        sys.exit(1)
    else:
        result = read_note(args.note_id, args.xsec_token)

    if "error" in result:
        print(f"Error: {result['error']}")
        sys.exit(1)

    print(f"\n{'='*50}")
    print(f"  {result['title']}")
    print(f"{'='*50}")
    print()
    for line in result["content"]:
        print(line)
    if result["hashtags"]:
        print()
        print(" ".join(result["hashtags"]))
    if result["comments"]:
        print(f"\n--- Comments ({len(result['comments'])}) ---")
        for c in result["comments"][:10]:
            print(f"  {c}")


if __name__ == "__main__":
    main()
