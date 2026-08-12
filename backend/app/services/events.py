import asyncio
from datetime import datetime, timezone

_subscribers: list[asyncio.Queue] = []


def subscribe() -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue()
    _subscribers.append(q)
    return q


def unsubscribe(q: asyncio.Queue) -> None:
    if q in _subscribers:
        _subscribers.remove(q)


async def broadcast(event_type: str, description: str, entity_type: str | None = None, entity_id: int | None = None) -> None:
    payload = {
        "event_type": event_type,
        "description": description,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    for q in list(_subscribers):
        await q.put(payload)
