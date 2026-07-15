#!/usr/bin/env python3
"""
Download video from rednote.com using Playwright.
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

DEFAULT_SESSION = os.environ.get(
    "REDNOTE_SESSION",
    str(Path.home() / ".config" / "rednote" / "session.json")
)

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from urls import normalize_note_url  # noqa: E402


def download_video(url: str, output_dir: str = "~/Downloads/xhs",
                   session_file: str | None = None) -> str | None:
    """
    Download video from rednote.com.
    
    Returns path to downloaded file or None on failure.
    """
    session_file = session_file or DEFAULT_SESSION
    storage = Path(session_file)
    if not storage.exists():
        print(f"ERROR: Session file not found: {session_file}")
        print("Run: python3 -m src.login")
        return None

    try:
        url = normalize_note_url(url=url)
    except ValueError as e:
        print(f"ERROR: {e}")
        return None

    out = Path(output_dir).expanduser()
    out.mkdir(parents=True, exist_ok=True)

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

        print(f"Loading {url}...")
        
        # 拦截请求来获取视频 URL
        video_url = None
        
        def handle_route(route, request):
            nonlocal video_url
            req_url = request.url
            if '.mp4' in req_url and 'xhscdn' in req_url:
                video_url = req_url
                print(f"Found video URL: {req_url[:80]}...")
            route.continue_()
        
        page.route("**/*", handle_route)
        
        page.goto(url, timeout=30000)
        page.wait_for_load_state("networkidle", timeout=20000)
        time.sleep(5)
        
        # 如果没有从请求拦截到，尝试从页面获取
        if not video_url:
            print("Trying to get video from page...")
            video_info = page.evaluate("""
                () => {
                    const v = document.querySelector('video');
                    if (!v) {
                        const videos = document.querySelectorAll('video');
                        for (const vid of videos) {
                            if (vid.currentSrc || vid.src) {
                                return { src: vid.currentSrc || vid.src };
                            }
                        }
                        return null;
                    }
                    return { src: v.currentSrc || v.src };
                }
            """)
            if video_info and video_info.get('src'):
                video_url = video_info['src']
                print(f"Found video from page: {video_url[:80]}...")
        
        if not video_url:
            browser.close()
            print("ERROR: No video found on page")
            return None
        
        print(f"Video URL: {video_url[:80]}...")
        
        # Get note info for filename
        note_data = page.evaluate("""
            () => {
                try {
                    const desc = document.querySelector('.desc')?.textContent?.slice(0, 30) || '';
                    const author = document.querySelector('.author')?.textContent || 'unknown';
                    return { desc, author };
                } catch(e) {
                    return { desc: '', author: 'unknown' };
                }
            }
        """)
        
        safe_author = note_data.get('author', 'unknown').replace('/', '_')[:20]
        filename = f"{safe_author}_{int(time.time())}.mp4"
        output_path = out / filename
        
        # Save cache for fast mode
        cache_key = hashlib.md5(url.encode()).hexdigest()[:8]
        cache_file = out / f".video_cache_{cache_key}.json"
        with open(cache_file, 'w') as f:
            json.dump({'video_url': video_url, 'filename': filename}, f)
        
        browser.close()
        
        # Download video using curl
        print(f"Downloading to {output_path}...")
        result = subprocess.run(
            ['curl', '-sL', video_url,
             '-H', 'User-Agent: Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X)',
             '-H', 'Referer: https://www.rednote.com/',
             '-o', str(output_path)],
            capture_output=True, timeout=120
        )
        
        if result.returncode == 0 and output_path.exists():
            size = output_path.stat().st_size
            print(f"✅ Downloaded: {output_path} ({size/1024/1024:.1f}MB)")
            return str(output_path)
        else:
            print(f"ERROR: Download failed")
            return None


def download_video_fast(url: str, output_dir: str = "~/Downloads/xhs") -> str | None:
    """
    快速下载视频 - 如果缓存存在直接下载，否则走浏览器流程
    """
    out = Path(output_dir).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    
    # 生成缓存 key
    cache_key = hashlib.md5(url.encode()).hexdigest()[:8]
    cache_file = out / f".video_cache_{cache_key}.json"
    
    # 检查缓存
    if cache_file.exists():
        print("使用缓存的视频 URL...")
        with open(cache_file) as f:
            cached = json.load(f)
        video_url = cached.get('video_url')
        if video_url:
            filename = cached.get('filename', f'video_{cache_key}.mp4')
            output_path = out / filename
            print(f"Downloading from cache...")
            result = subprocess.run(
                ['curl', '-sL', video_url,
                 '-H', 'User-Agent: Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X)',
                 '-H', 'Referer: https://www.rednote.com/',
                 '-o', str(output_path)],
                capture_output=True, timeout=60
            )
            if result.returncode == 0 and output_path.exists():
                size = output_path.stat().st_size
                print(f"✅ Downloaded: {output_path} ({size/1024/1024:.1f}MB)")
                return str(output_path)
            else:
                print("缓存下载失败，重新获取...")
    
    # 缓存不存在或下载失败，走完整流程
    return download_video(url, output_dir)


def main():
    parser = argparse.ArgumentParser(description="Download video from rednote.com")
    parser.add_argument("--url", required=True, help="Video URL")
    parser.add_argument("-o", "--output-dir", default="~/Downloads/xhs", help="Output directory")
    parser.add_argument("--fast", action="store_true", help="Use cache if available")
    args = parser.parse_args()

    if args.fast:
        result = download_video_fast(args.url, args.output_dir)
    else:
        result = download_video(args.url, args.output_dir)
    
    if result:
        print(result)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
