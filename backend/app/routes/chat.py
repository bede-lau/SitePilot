"""ARD §5.1/§5.5 — dashboard chat. POST /api/chat/stream is the demo's spine:
an SSE wrapper around agents/orchestrator.run_orchestrator_stream.

Uses its own AsyncSessionLocal (like the background tasks in
agents/procurement.py) rather than the request-scoped Depends(get_db) — a
generator-dependency's session is torn down as soon as the route handler
*returns* the Response object, which for a streaming response is before the
body generator actually runs, so a `Depends(get_db)` session would already be
closed by the time run_orchestrator_stream tries to use it."""
import json
import logging

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.agents.orchestrator import CAPABILITY_REPLY, MAX_HISTORY_TURNS, run_orchestrator_stream
from app.config import settings
from app.database import AsyncSessionLocal, get_db
from app.models.models import ChatMessage
from app.schemas import ChatRequest

logger = logging.getLogger("fieldbot.chat")

router = APIRouter(prefix="/api/chat", tags=["chat"])


async def _load_history(db: AsyncSession, session_key: str) -> list[dict]:
    rows = (
        await db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_key == session_key)
            .order_by(ChatMessage.created_at.desc())
            .limit(MAX_HISTORY_TURNS * 2)
        )
    ).scalars().all()
    return [{"role": r.role, "content": r.content} for r in reversed(rows) if r.role in ("user", "assistant")]


@router.get("/history")
async def get_history(session_key: str, db: AsyncSession = Depends(get_db)):
    rows = (
        await db.execute(
            select(ChatMessage).where(ChatMessage.session_key == session_key).order_by(ChatMessage.created_at.asc())
        )
    ).scalars().all()
    return [
        {
            "id": r.id,
            "role": r.role,
            "content": r.content,
            "cards": r.cards,
            "attachments": r.attachments,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@router.post("")
async def chat_once(payload: ChatRequest):
    """Non-streaming fallback (ARD §5.1) — drains the same event stream used
    by /stream and collapses it to {reply, cards}."""
    async with AsyncSessionLocal() as db:
        history = await _load_history(db, payload.session_key)
        reply_parts: list[str] = []
        cards: list[dict] = []
        async for event in run_orchestrator_stream(
            db, payload.session_key, settings.demo_phone_number, payload.message, history, payload.attachments
        ):
            if event["type"] == "delta":
                reply_parts.append(event["text"])
            elif event["type"] == "card":
                cards.append({"card_type": event["card_type"], "data": event["data"]})
            elif event["type"] == "error":
                return {"reply": f"Something went wrong: {event['message']}", "cards": []}
        return {"reply": "".join(reply_parts).strip() or CAPABILITY_REPLY, "cards": cards}


@router.post("/stream")
async def chat_stream(payload: ChatRequest):
    async def event_generator():
        async with AsyncSessionLocal() as db:
            history = await _load_history(db, payload.session_key)
            async for event in run_orchestrator_stream(
                db, payload.session_key, settings.demo_phone_number, payload.message, history, payload.attachments
            ):
                yield {"event": "message", "data": json.dumps(event, default=str)}

    return EventSourceResponse(event_generator(), ping=15)
