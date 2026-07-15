#!/usr/bin/env python3
"""
Analyze video content from a rednote.com note WITHOUT downloading the file.
Uses headless Playwright to play the video and capture keyframes.

Usage:
  python -m src.video --note-id <id> --xsec-token <token> [--frames 5]
"""

import argparse, json, os, sys, time
from pathlib import Path

DEFAULT_SESSION = os.environ.get(
    "REDNOTE_SESSION",
    str(Path.home() / ".config" / "rednote" / "session.json")
)
FRAME_DIR = Path("/tmp/rednote_frames")

from playwright.sync_api import sync_playwright

from .urls import normalize_note_url


def analyze_video(note_id: str, xsec_token: str | None = None,
                  url: str | None = None,
                  frame_count: int = 5,
                  session_file: str | None = None) -> dict:
    """
    Play a rednote video in headless Playwright, capture keyframes.
    
    Returns dict with keys:
      duration: float (seconds)
      frames: list of {"ts": float, "path": str} (paths to PNG screenshots)
      error: str (if something went wrong)
    """
    session_file = session_file or DEFAULT_SESSION
    storage = Path(session_file)
    if not storage.exists():
        return {"error": f"Session file not found: {session_file}"}

    FRAME_DIR.mkdir(parents=True, exist_ok=True)

    try:
        base_url = normalize_note_url(url=url, note_id=note_id, xsec_token=xsec_token)
    except ValueError as e:
        return {"error": str(e)}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            storage_state=str(storage),
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/134.0.0.0 Safari/537.36"
            ),
            viewport={"width": 800, "height": 900},
        )
        page = ctx.new_page()

        page.goto(base_url, timeout=30000)
        page.wait_for_load_state("networkidle", timeout=20000)
        time.sleep(3)

        # Get video info
        info = page.evaluate("""
            () => {
                const v = document.querySelector('video');
                if (!v) return null;
                return {
                    duration: v.duration,
                    width: v.videoWidth,
                    height: v.videoHeight,
                    readyState: v.readyState
                };
            }
        """)
        if not info:
            browser.close()
            return {"error": "No video element found on page"}

        duration = info["duration"]
        n = min(frame_count, max(2, int(duration)))

        # Calculate evenly-spaced timestamps
        timestamps = []
        if duration <= 3:
            timestamps = [0.5, duration - 0.3]
        else:
            for i in range(n):
                t = duration * (i + 0.5) / n
                timestamps.append(min(t, duration - 0.3))

        frames = []
        for i, ts in enumerate(timestamps):
            try:
                page.evaluate(f"document.querySelector('video').currentTime = {ts}")
                time.sleep(1.2)

                clip = page.evaluate("""
                    () => {
                        const v = document.querySelector('video');
                        if (!v) return null;
                        const r = v.getBoundingClientRect();
                        if (r.width < 10) return null;
                        return {x: r.x, y: r.y, width: r.width, height: r.height};
                    }
                """)
                if clip:
                    path = str(FRAME_DIR / f"frame_{i:02d}.png")
                    page.screenshot(path=path, clip=clip)
                    frames.append({"ts": round(ts, 1), "path": path})
            except Exception:
                pass

        browser.close()

    return {
        "duration": round(duration, 1),
        "frames": frames,
        "error": None,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Capture keyframes from a rednote video for analysis"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--note-id")
    group.add_argument("--url")
    parser.add_argument("--xsec-token")
    parser.add_argument("--frames", type=int, default=5)
    args = parser.parse_args()

    if args.url:
        result = analyze_video("", url=args.url, frame_count=args.frames)
    elif not args.xsec_token:
        print("ERROR: --xsec-token required with --note-id")
        sys.exit(1)
    else:
        result = analyze_video(args.note_id, args.xsec_token,
                               frame_count=args.frames)

    if result.get("error"):
        print(f"ERROR: {result['error']}")
        sys.exit(1)

    print(f"Duration: {result['duration']}s")
    print(f"Keyframes: {len(result['frames'])}")
    for f in result["frames"]:
        print(f"  @ {f['ts']}s -> {f['path']}")


if __name__ == "__main__":
    main()
