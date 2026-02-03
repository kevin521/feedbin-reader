# Feedbin Reader

A minimal, e-ink optimized web reader for [Feedbin](https://feedbin.com) RSS with full two-way sync.

![Screenshot](screenshot.png)

## Why?

Native Feedbin apps don't work well on e-ink devices:
- No volume button navigation
- Horizontal scrolling issues
- Slow, complex UIs

This reader is designed for e-ink with:
- **Clean, high-contrast UI** - Black and white, large tap targets
- **One article at a time** - No infinite scroll or complex navigation
- **Arrow key navigation** - Works with EinkBro's volume button mapping
- **Full-text extraction** - Uses Feedbin's Mercury parser with trafilatura fallback
- **Two-way sync** - Mark as read/starred syncs back to Feedbin

## Features

- Shows unread articles one at a time (newest first)
- Filter by feed via dropdown
- Full extracted content (not just RSS snippets)
- Keyboard shortcuts: ← Prev, → Next, Enter = Mark Read, S = Star
- JSON API for custom clients

## Setup

### 1. Clone and configure

```bash
git clone https://github.com/YOUR_USERNAME/feedbin-reader.git
cd feedbin-reader
cp .env.example .env
```

Edit `.env` with your Feedbin credentials:

```
FEEDBIN_USER=your_feedbin_email
FEEDBIN_PASS=your_feedbin_password
```

### 2. Run with Docker

```bash
docker build -t feedbin-reader .
docker run -d \
  --name feedbin-reader \
  --restart unless-stopped \
  -p 5050:5000 \
  --env-file .env \
  feedbin-reader
```

Access at `http://localhost:5050`

### 3. Rebuild after changes

```bash
docker rm -f feedbin-reader
docker build -t feedbin-reader .
docker run -d \
  --name feedbin-reader \
  --restart unless-stopped \
  -p 5050:5000 \
  --env-file .env \
  feedbin-reader
```

## API

For custom e-ink clients, there's a JSON API:

### Get current article

```
GET /api/article?pos=0&feed=123
```

Returns:
```json
{
  "total": 42,
  "position": 0,
  "article": {
    "id": 12345,
    "title": "Article Title",
    "feed": "Feed Name",
    "date": "2024-01-15",
    "url": "https://...",
    "content": "Full text..."
  },
  "feeds": [{"id": 1, "title": "Feed 1"}, ...]
}
```

### Mark as read

```
POST /api/mark_read
Content-Type: application/json

{"id": 12345}
```

### Star article

```
POST /api/star
Content-Type: application/json

{"id": 12345}
```

## License

MIT
