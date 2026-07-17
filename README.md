# Rednote Reader

A headless tool to read notes from [rednote.com](https://www.rednote.com) (小红书 international domain) — text, images, and video analysis — without opening a visible browser window.

**What it is:**
- Reads text captions, hashtags, and comments from a note
- Extracts image URLs from the photo slider
- Captures video keyframes for visual analysis (no file download needed)
- Your own session, your own browsing — not a crawler or scraper

**What it is not:**
- Not a bulk downloader or archiver
- Not an API — it uses headless Playwright, like opening the page in a browser
- No bypass of login walls, anti-bot protections, or paywalls

## Quick Start

```bash
# 1. Install
pip install playwright
playwright install chromium

# 2. Login once
python -m src.login
# ^^ Scans a QR code with the rednote app to save your session

# 3. Read a note
python -m src.reader --url "https://www.rednote.com/explore/<id>?xsec_token=<token>"
```

## Usage

### Login (one-time setup)

Opens a visible browser window to scan a QR code. Saves cookies to `~/.config/rednote/session.json`. Run again when cookies expire (typically every few weeks).

```bash
python -m src.login
```

You can set a custom session path via the `REDNOTE_SESSION` environment variable.

### Reading text

```bash
# From a shortlink (xhslink.com)
curl -sL -A "Mozilla/5.0" "http://xhslink.com/o/<code>" \
  -o /dev/null -w '%{url_effective}'
# ^^ Gives you the full URL with note_id and xsec_token

# Then read
python -m src.reader --url "https://www.rednote.com/explore/<id>?xsec_token=<token>"

# Or
python -m src.reader --note-id <id> --xsec-token <token>
```

Output: title, body text, hashtags, comments.

### Extracting images

```bash
# Print image URLs (no download)
python -m src.images --note-id <id> --xsec-token <token>

# Download to /tmp/rednote_images (default: no-watermark HD version)
python -m src.images --note-id <id> --xsec-token <token> --download

# Download with watermark (original web version)
python -m src.images --note-id <id> --xsec-token <token> --download --with-watermark
```

**Image Quality Options:**

| Option | Quality | Watermark | Format | Size |
|--------|---------|-----------|--------|------|
| Default (no args) | HD (up to original) | ❌ No | JPEG | 2-10MB |
| `--with-watermark` | 1080px | ✅ Yes | JPEG | ~300KB |

The default `--download` now fetches **original HEIF images** from `sns-na-i11.xhscdn.com` and converts them to high-quality JPEG (95% quality). These are the original uploaded files without platform watermarks.

### Analyzing videos (no file download)

Captures screenshots of keyframes from the video playing in the headless browser. Output PNG files for visual analysis.

```bash
python -m src.video --note-id <id> --xsec-token <token> --frames 5
```

Use a vision-capable model on the output frames to understand the video content without ever downloading the mp4 file.

### Downloading full video (with yt-dlp)

To download the complete video as an MP4 file (requires `yt-dlp`):

```bash
# Install yt-dlp
pip install yt-dlp

# Download video using shortlink
yt-dlp --cookies-from-browser chrome --referer "https://www.xiaohongshu.com/" \
  "http://xhslink.com/o/<code>"

# Or using full URL
yt-dlp --cookies-from-browser chrome --referer "https://www.xiaohongshu.com/" \
  "https://www.rednote.com/explore/<id>?xsec_token=<token>"
```

**Features:**
- Downloads original MP4 file (no platform watermark)
- Preserves original quality
- Requires Chrome/Chromium session (already logged in)
- Works with both xhslink shortlinks and full rednote.com URLs

### Searching for notes

```bash
python -m src.search "穿搭" --max 20
python -m src.search "武康路 街拍"
```

Returns note IDs and titles. Results can then be passed to `reader` or `images` directly — notes found via search **do not require xsec_token** for access.

## How it works

1. **Playwright** launches a headless Chromium browser
2. Loads the rednote.com page with your saved session cookies
3. **Text:** reads the rendered DOM (`innerText`)
4. **Images:** extracts `<img>` URLs from the Swiper slider (CDN: `sns-web-i10.rednotecdn.com`)
5. **Video:** uses `HTMLVideoElement.currentTime` to seek through the video, captures screenshots of each frame
6. Browser is then closed — no state persists

## Project structure

```
rednote-reader/
├── src/
│   ├── __init__.py
│   ├── login.py      # QR code login → saves session
│   ├── search.py     # Search notes by keyword
│   ├── reader.py     # Text extraction
│   ├── images.py     # Image URL extraction & download
│   └── video.py      # Video keyframe capture
├── requirements.txt
├── LICENSE
└── README.md
```

## Notes

- Requires a valid **rednote.com login session** — the tool does not bypass authentication
- Image CDN domain: `sns-web-i10.rednotecdn.com` (not `xhscdn.com`)
- Video CDN domain: `sns-v8.rednotecdn.com`
- Designed for personal use on notes you can already access via browser

## License

MIT
