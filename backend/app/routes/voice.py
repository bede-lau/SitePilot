"""ARD §5.1/§8 — /api/voice/transcribe and /api/voice/speak (dashboard mic)."""
from fastapi import APIRouter, File, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from app.services.voice import speak, transcribe

router = APIRouter(prefix="/api/voice", tags=["voice"])


class SpeakRequest(BaseModel):
    text: str
    voice_id: str | None = None


@router.post("/transcribe")
async def transcribe_endpoint(audio: UploadFile = File(...)):
    content = await audio.read()
    result = await transcribe(content, audio.filename or "audio.webm", audio.content_type or "audio/webm")
    return {"text": result["text"], "duration_s": None, "language": result.get("language_code")}


@router.post("/speak")
async def speak_endpoint(payload: SpeakRequest):
    audio_bytes = await speak(payload.text, payload.voice_id)
    if audio_bytes is None:
        return Response(status_code=204)
    return Response(content=audio_bytes, media_type="audio/mpeg")
