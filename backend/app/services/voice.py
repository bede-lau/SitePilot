"""ARD §8 — ElevenLabs voice, plain httpx (no SDK), same stub discipline as the
existing Telegram/SMTP integrations: with no ELEVENLABS_API_KEY the app stays
fully runnable (STT returns a fixed field note, TTS returns None -> caller
sends 204)."""
import logging

import httpx

from app.config import settings

logger = logging.getLogger("fieldbot.voice")

STT_URL = "https://api.elevenlabs.io/v1/speech-to-text"
TTS_URL_TMPL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

STUB_TRANSCRIPT = "Site has minimal shading, standard metal deck roof."


async def transcribe(audio_bytes: bytes, filename: str, content_type: str = "audio/mpeg") -> dict:
    """Returns {text, language_code}. Stub when no key configured."""
    if not settings.voice_enabled:
        logger.info("[voice:stub] transcribe called without ELEVENLABS_API_KEY (%d bytes)", len(audio_bytes))
        return {"text": STUB_TRANSCRIPT, "language_code": "en"}

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            STT_URL,
            headers={"xi-api-key": settings.elevenlabs_api_key},
            data={"model_id": settings.elevenlabs_stt_model},
            files={"file": (filename, audio_bytes, content_type or "application/octet-stream")},
        )
        resp.raise_for_status()
        data = resp.json()
    return {"text": data.get("text", ""), "language_code": data.get("language_code")}


async def speak(text: str, voice_id: str | None = None) -> bytes | None:
    """Returns MP3 bytes, or None when voice is unavailable (no key, or no
    voice_id resolvable) — caller should respond 204 in that case."""
    if not settings.voice_enabled:
        logger.info("[voice:stub] speak called without ELEVENLABS_API_KEY")
        return None

    vid = voice_id or settings.elevenlabs_voice_id
    if not vid:
        logger.warning("speak called without a voice_id and ELEVENLABS_VOICE_ID unset")
        return None

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{TTS_URL_TMPL.format(voice_id=vid)}?output_format=mp3_44100_128",
            headers={"xi-api-key": settings.elevenlabs_api_key},
            json={"text": text, "model_id": "eleven_turbo_v2_5"},
        )
        resp.raise_for_status()
        return resp.content
