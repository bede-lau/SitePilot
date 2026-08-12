import asyncio
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

from app.services.events import subscribe, unsubscribe

router = APIRouter()


@router.get("/events")
async def stream_events(request: Request):
    queue = subscribe()

    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=10)
                except asyncio.TimeoutError:
                    payload = {
                        "event_type": "heartbeat",
                        "description": "test event",
                        "entity_type": None,
                        "entity_id": None,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                yield {"event": "message", "data": json.dumps(payload)}
        finally:
            unsubscribe(queue)

    return EventSourceResponse(event_generator())
