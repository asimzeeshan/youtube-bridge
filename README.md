# youtube-bridge

Self-hosted YouTube transcript bridge. Extracts transcripts from YouTube videos via a simple REST API - tries existing captions first, falls back to Whisper audio transcription.

No API keys required. No YouTube Data API quotas. Just a lightweight FastAPI service with two-tier transcript extraction.

## How it works

```
Request -> Try YouTube captions (instant)
              |
              v
           Found? -> Return transcript
              |
              No
              v
         Download audio via yt-dlp
              |
              v
         Transcribe with faster-whisper (CPU)
              |
              v
         Return transcript
```

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check (includes loaded Whisper model) |
| `GET` | `/transcript/{video_id}` | Get transcript for a YouTube video |
| `GET` | `/docs` | Interactive Swagger docs |

### Query parameters

| Param | Default | Description |
|-------|---------|-------------|
| `lang` | `en` | Preferred caption language (tries this first, then `en`, `ur`, `hi`) |
| `force_whisper` | `false` | Skip captions entirely, always use Whisper |

### Example: Get a transcript

```bash
curl -s http://localhost:8000/transcript/dQw4w9WgXcQ
```

```json
{
  "video_id": "dQw4w9WgXcQ",
  "source": "captions",
  "detected_language": null,
  "transcript": "We're no strangers to love...",
  "title": "Rick Astley - Never Gonna Give You Up",
  "channel": "Rick Astley",
  "duration": "213",
  "description": "The official video for..."
}
```

### Example: Force Whisper transcription

```bash
curl -s "http://localhost:8000/transcript/dQw4w9WgXcQ?force_whisper=true"
```

### Example: Prefer Urdu captions

```bash
curl -s "http://localhost:8000/transcript/dQw4w9WgXcQ?lang=ur"
```

## Setup

### 1. Clone and configure

```bash
git clone https://github.com/asimzeeshan/youtube-bridge.git
cd youtube-bridge
cp .env.example .env
# Edit .env if you want to change the Whisper model
```

### 2. Run with Docker Compose

```bash
docker compose up -d
```

The service will be available at `http://localhost:8000`.

### With nginx-proxy (automatic SSL)

If you're running [nginx-proxy-automation](https://github.com/evertramos/nginx-proxy-automation) with Let's Encrypt, set `VIRTUAL_HOST`, `LETSENCRYPT_HOST`, and `LETSENCRYPT_EMAIL` in your `.env` file.

## Whisper models

The Whisper fallback model can be configured via the `WHISPER_MODEL` environment variable:

| Model | Size | Speed | Accuracy |
|-------|------|-------|----------|
| `tiny` | 39 MB | Fastest | Lower |
| `base` | 74 MB | Fast | Good (default) |
| `small` | 244 MB | Moderate | Better |
| `medium` | 769 MB | Slow | High |
| `large-v3` | 1.5 GB | Slowest | Highest |

The model is loaded lazily on the first Whisper transcription request. Container memory limit is set to 2GB by default - increase this if using larger models.

## Dependencies

Bundled inside the Docker image:
- **yt-dlp** - YouTube audio download
- **youtube-transcript-api** - Caption extraction
- **faster-whisper** - Audio transcription (CTranslate2)
- **ffmpeg** - Audio format conversion
- **deno** - Required by yt-dlp for YouTube JS extraction

## Notes

- Caption extraction is near-instant. Whisper fallback takes 10-60s depending on video length and model size.
- The `cache/` directory is volume-mounted but currently unused - reserved for future caching.
- Memory limit is 2GB by default. The `base` model fits comfortably; for `medium` or `large-v3`, increase the limit.

## Author

[Asim Zeeshan](https://www.linkedin.com/in/asimzeeshan/)

## License

[MIT](LICENSE)
