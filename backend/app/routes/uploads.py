"""ARD §5.1 — POST /api/uploads.

Generic file intake for the dashboard: quote PDFs/images dropped into chat,
and (via routes/voice.py) recorded audio. Writes into backend/uploads/ (already
mounted at /static/uploads in main.py) under a kind-specific subdirectory and
returns a stable file_id — the bare filename, since it's already
collision-proof (uuid4 prefix) and is all routes/quotes.py needs to re-open it.
"""
import logging
import mimetypes
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.config import settings

logger = logging.getLogger("fieldbot.uploads")

router = APIRouter(prefix="/api/uploads", tags=["uploads"])

UPLOAD_ROOT = Path("uploads")
KIND_DIRS = {"pdf": "quotes", "image": "images", "audio": "audio", "other": "misc"}


def _classify(filename: str, content_type: str | None) -> str:
    ct = (content_type or "").lower()
    ext = Path(filename).suffix.lower()
    if ct == "application/pdf" or ext == ".pdf":
        return "pdf"
    if ct.startswith("image/") or ext in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
        return "image"
    if ct.startswith("audio/") or ext in (".mp3", ".wav", ".m4a", ".ogg", ".webm"):
        return "audio"
    return "other"


def resolve_upload_path(file_id: str) -> Path | None:
    """Used by routes/quotes.py and routes/voice.py to re-open a previously
    uploaded file by its file_id, without trusting a client-supplied path."""
    if "/" in file_id or "\\" in file_id or ".." in file_id:
        return None
    for subdir in KIND_DIRS.values():
        candidate = UPLOAD_ROOT / subdir / file_id
        if candidate.exists():
            return candidate
    return None


@router.post("")
async def upload_file(file: UploadFile = File(...)):
    kind = _classify(file.filename or "", file.content_type)
    subdir = KIND_DIRS[kind]
    target_dir = UPLOAD_ROOT / subdir
    target_dir.mkdir(parents=True, exist_ok=True)

    ext = Path(file.filename or "").suffix or mimetypes.guess_extension(file.content_type or "") or ""
    file_id = f"{uuid.uuid4().hex}{ext}"
    dest = target_dir / file_id

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")
    dest.write_bytes(content)

    url = f"/static/uploads/{subdir}/{file_id}"
    logger.info("uploaded file_id=%s kind=%s size=%d", file_id, kind, len(content))
    return {
        "file_id": file_id,
        "filename": file.filename,
        "url": url,
        "kind": kind,
        "size": len(content),
    }
