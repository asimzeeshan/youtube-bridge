import os
import re
import logging
import tempfile
import subprocess
from pathlib import Path
from fastapi import FastAPI, HTTPException, Query

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("youtube-bridge")

app = FastAPI(title="youtube-bridge", docs_url="/docs")

WHISPER_MODEL = os.environ.get("WHISPER_MODEL", "base")
whisper_model = None


def get_video_id(url_or_id: str) -> str:
    """Extract video ID from various YouTube URL formats."""
    patterns = [
        r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})",
        r"^([a-zA-Z0-9_-]{11})$",
    ]
    for pattern in patterns:
        match = re.search(pattern, url_or_id)
        if match:
            return match.group(1)
    return url_or_id


def get_captions(video_id: str, lang: str = "en"):
    """Try to get existing captions via youtube-transcript-api."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi

        ytt = YouTubeTranscriptApi()
        transcript = ytt.fetch(video_id, languages=[lang, "en", "ur", "hi"])
        lines = []
        for snippet in transcript.snippets:
            lines.append(snippet.text)
        return " ".join(lines), "captions"
    except Exception as e:
        logger.info(f"No captions available for {video_id}: {e}")
        return None, None


def get_video_metadata(video_id: str):
    """Get video title, channel, duration via yt-dlp."""
    try:
        result = subprocess.run(
            [
                "yt-dlp",
                "--no-download",
                "--print", "%(title)s|||%(channel)s|||%(duration)s|||%(description)s",
                f"https://www.youtube.com/watch?v={video_id}",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            parts = result.stdout.strip().split("|||")
            return {
                "title": parts[0] if len(parts) > 0 else "",
                "channel": parts[1] if len(parts) > 1 else "",
                "duration": parts[2] if len(parts) > 2 else "",
                "description": parts[3][:500] if len(parts) > 3 else "",
            }
    except Exception as e:
        logger.warning(f"Failed to get metadata: {e}")
    return {}


def transcribe_audio(video_id: str):
    """Download audio and transcribe with faster-whisper."""
    global whisper_model
    if whisper_model is None:
        from faster_whisper import WhisperModel

        logger.info(f"Loading whisper model: {WHISPER_MODEL}")
        whisper_model = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
        logger.info("Whisper model loaded")

    with tempfile.TemporaryDirectory() as tmpdir:
        audio_path = os.path.join(tmpdir, "audio.wav")
        result = subprocess.run(
            [
                "yt-dlp",
                "-x",
                "--audio-format", "wav",
                "--audio-quality", "0",
                "-o", audio_path.replace(".wav", ".%(ext)s"),
                "--no-playlist",
                f"https://www.youtube.com/watch?v={video_id}",
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            raise Exception(f"yt-dlp failed: {result.stderr[:300]}")

        wav_files = list(Path(tmpdir).glob("audio*"))
        if not wav_files:
            raise Exception("No audio file produced")
        actual_path = str(wav_files[0])

        segments, info = whisper_model.transcribe(actual_path, beam_size=5)
        text_parts = []
        for segment in segments:
            text_parts.append(segment.text.strip())

        return " ".join(text_parts), info.language


@app.get("/health")
async def health():
    return {"status": "ok", "whisper_model": WHISPER_MODEL}


@app.get("/transcript/{video_id_or_url:path}")
async def get_transcript(
    video_id_or_url: str,
    lang: str = Query("en", description="Preferred caption language"),
    force_whisper: bool = Query(False, description="Skip captions, force Whisper transcription"),
):
    video_id = get_video_id(video_id_or_url)

    metadata = get_video_metadata(video_id)

    transcript = None
    source = None
    detected_language = None

    if not force_whisper:
        transcript, source = get_captions(video_id, lang)

    if transcript is None:
        try:
            transcript, detected_language = transcribe_audio(video_id)
            source = "whisper"
        except Exception as e:
            logger.exception("Whisper transcription failed")
            raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")

    return {
        "video_id": video_id,
        "source": source,
        "detected_language": detected_language,
        "transcript": transcript,
        **metadata,
    }
