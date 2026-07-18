# Rednote Reader

A personal toolkit for reading notes from Xiaohongshu / RedNote (小红书). It supports text, images, and video via multiple strategies:

1. **`xiaohongshu-cli` (`xhs`)** — preferred, API-first, no browser needed
2. **`rednote-reader` (this repo)** — Playwright fallback when `xhs` fails or session expires
3. **Scraping / CDN extraction** — last-resort fallback for video/images

**What it is:**
- Reads text captions, hashtags, and comments from a note
- Extracts image URLs (including no-watermark HD originals)
- Captures video keyframes for visual analysis
- Downloads full MP4 when needed
- Cross-checks factual claims using Exa / authoritative sources

**What it is not:**
- Not a bulk downloader or archiver
- Not an official API
- No bypass of login walls, anti-bot protections, or paywalls

---

## Quick Start

```bash
# Install the preferred CLI (requires Chrome for session refresh)
pip install xiaohongshu-cli

# Read a note directly (supports xhslink, xiaohongshu.com, rednote.com)
xhs read "http://xhslink.com/o/xxxxx"
xhs read "<url>" --json

# Download images
xhs images "<url>" --download -o /tmp/my_images

# Download video
xhs video "<url>" --download -o /tmp/video.mp4
```

If `xhs` fails, fall back to the Playwright-based `rednote-reader` below.

---

## Strategy overview

```
URL ──► xhs read / images / video ──► success? ──► done
                              │
                              ▼ fail
                  rednote-reader (Playwright)
                              │
                              ▼ fail
                  curl + SSR / CDN extraction
```

**Hermes skill version**: `~/.hermes/skills/social-media/rednote-content-reader/SKILL.md`

---

## 1. xiaohongshu-cli (preferred)

`xhs` uses the Xiaohongshu internal API directly. Session cookies are pulled from Chrome automatically and refreshed periodically.

### Read note

```bash
xhs read "<url>"
xhs read "<url>" --json
xhs read "<url>" --yaml
```

- Accepts `xhslink.com`, `xiaohongshu.com`, `rednote.com`
- No need to manually expand shortlinks

### Images

```bash
xhs images "<url>"          # list URLs
xhs images "<url>" --download -o /tmp/my_images
```

### Video

```bash
xhs video "<url>"           # list video URL
xhs video "<url>" --download -o /tmp/video.mp4
```

### Comments and search

```bash
xhs comments "<url>" --all --json
xhs search "关键词" --sort popular --type video
```

### When `xhs` fails

Common failures:
- `No video found in this note` — extract `video.media.stream.h264/h265[].masterUrl` from `xhs read --json` and `curl` download directly
- Captcha — wait and retry, or switch to `rednote-reader`

---

## 2. rednote-reader (Playwright fallback)

### Setup

```bash
pip install -r requirements.txt
playwright install chromium
```

### Login

```bash
python -m src.login
```

Scans a QR code with the RedNote app and saves cookies to `~/.config/rednote/session.json`. Re-run when cookies expire.

### Read text

```bash
# From a shortlink: first resolve it
curl -sL -A "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36" \
  -H "Referer: https://www.xiaohongshu.com" \
  "http://xhslink.com/o/<code>" -o /dev/null -w '%{url_effective}'

# Then read
python -m src.reader --url "https://www.rednote.com/explore/<id>?xsec_token=<token>"
# or
python -m src.reader --note-id <id> --xsec-token <token>
```

### Images

```bash
rm -rf /tmp/rednote_images/   # always clear cache first
python -m src.images --url "<url>" --download
```

Default download fetches original HEIF images from `sns-na-i11.xhscdn.com` and converts to high-quality JPEG without platform watermark.

### Video keyframes

```bash
python -m src.video --url "<url>" --frames 5
```

Captures PNG screenshots of keyframes for visual analysis without downloading the MP4.

### Search

```bash
python -m src.search "穿搭" --max 20
```

---

## 3. Scraping / CDN fallbacks

### Full video download with yt-dlp

```bash
yt-dlp --cookies-from-browser chrome --referer "https://www.xiaohongshu.com/" \
  "http://xhslink.com/o/<code>"
```

### Extract SSR data

```bash
curl -sL -A "Mozilla/5.0 (Linux; Android 14)" \
  -H "Referer: https://www.rednote.com/" \
  "https://www.rednote.com/explore/<id>?xsec_token=<token>" \
  -o /tmp/xhs.html
```

Then parse `window.__INITIAL_STATE__` from `/tmp/xhs.html`.

### No-watermark HD images

1. Extract `fileId` from SSR: `note.noteDetailMap[<id>].noteData.imageList[].fileId`
2. Download original HEIF:

```bash
curl -sL "http://sns-na-i11.xhscdn.com/<fileId>" \
  -H "Referer: https://www.rednote.com/" -o image.heif
sips -s format jpeg -s formatOptions 95 image.heif --out image.jpg
```

---

## 4. Fact-checking workflow

When a note contains verifiable claims (policy changes, news, product launches, health/finance advice):

1. Extract specific claims: people, institutions, dates, numbers, policy terms
2. Search authoritative sources via Exa / web search (`site:dhs.gov`, `site:federalregister.gov`, mainstream outlets)
3. Cross-check at least two independent sources
4. Label each claim:
   - **Verified** — supported by authoritative source
   - **Partially verified** — some details differ or only second-hand coverage
   - **Unverified** — no reliable source found
   - **False / misleading** — contradicts authoritative sources

Example: a note claiming DHS changed F-1 rules was verified against Fragomen, Envoy Global, NAFSA, and the Federal Register before reporting back.

---

## Session management

- **Path**: `~/.config/rednote/session.json`
- **Typical lifetime**: days to weeks; `web_session` may last 24–48 hours
- **Refresh**: `xhs` auto-refreshes from Chrome; `rednote-reader` can use `session_keepalive.py`
- **Re-login**: `python -m src.login` (or `headless_login_qr.py` for headless QR capture)

---

## Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| `xhs` captcha | rate-limit | cool down or switch to `rednote-reader` |
| `xhs video` returns `No video found` | parser mismatch | use `xhs read --json` → extract `masterUrl` → `curl` download |
| `TimeoutError: 20000ms exceeded` (images/video/search) | `networkidle` never reached | change `networkidle` to `domcontentloaded` in source |
| Login wall / QR page | session expired | re-run `src.login` or use `headless_login_qr.py` |
| Mixed old/new images | cache not cleared | `rm -rf /tmp/rednote_images/` before download |
| Note 404 / "暂时无法浏览" | deleted/private/removed | cannot recover; tell user the note is unavailable |

---

## Project structure

```
rednote-reader/
├── src/
│   ├── __init__.py
│   ├── login.py              # QR login → saves session
│   ├── search.py             # Search notes
│   ├── reader.py             # Text extraction
│   ├── images.py             # Image URL extraction & download
│   ├── video.py              # Video keyframe capture
│   ├── session.py            # Session helpers
│   ├── urls.py               # URL parsing utilities
│   └── ...
├── scripts/                  # Helper scripts
├── requirements.txt
├── LICENSE
└── README.md
```

---

## License

MIT
