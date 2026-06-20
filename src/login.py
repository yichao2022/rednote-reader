#!/usr/bin/env python3
"""
Login to rednote.com via QR code and save session for later use.
One-time setup; run again only when cookies expire.
"""

import json, os, sys, time
from pathlib import Path

DEFAULT_SESSION_FILE = os.environ.get(
    "REDNOTE_SESSION",
    str(Path.home() / ".config" / "rednote" / "session.json")
)

from playwright.sync_api import sync_playwright


def login(session_file: str | None = None) -> str:
    """
    Open a browser, let the user scan the QR code, save the session.
    
    Returns the path to the saved session file.
    """
    session_file = session_file or DEFAULT_SESSION_FILE
    session_path = Path(session_file)
    session_path.parent.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("  rednote.com — Login")
    print("=" * 60)
    print()
    print("1. A browser window will open to rednote.com")
    print("2. Scan the QR code with the rednote (Xiaohongshu) app")
    print("3. After successful login, return here and press Enter")
    print("4. Your session will be saved")
    print()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--window-size=1280,900"]
        )
        ctx = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/134.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
        )
        page = ctx.new_page()
        page.goto("https://www.rednote.com", timeout=30000)

        print("Browser opened. Scan the QR code with the rednote app.")
        print("Press Enter here after logging in...")
        try:
            input()
        except (EOFError, KeyboardInterrupt):
            print("\nLogin cancelled.")
            browser.close()
            sys.exit(1)

        state = ctx.storage_state()
        with open(session_path, "w") as f:
            json.dump(state, f, indent=2)

        cookies = state.get("cookies", [])
        a1 = next((c for c in cookies if c.get("name") == "a1"), None)
        if a1 and a1.get("value"):
            print(f"\n✅ Session saved: {session_file}")
            print(f"   Cookies captured: {len(cookies)}")
        else:
            print("\n⚠️  a1 cookie not found. Login may not have worked.")

        print("\nPress Enter to close the browser...")
        input()
        browser.close()

    return session_file


if __name__ == "__main__":
    login()
