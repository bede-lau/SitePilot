import asyncio
import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import Base, engine
from app.db_upgrade import run_upgrade
from app.models import models  # noqa: F401  (ensures models register on Base.metadata)
from app.routes import (
    analytics,
    chat,
    components,
    events,
    feasibility,
    inspections,
    invoices,
    overview,
    po,
    projects,
    purchase_orders,
    quotes,
    uploads,
    vendors,
    voice,
    webhook,
)
from app.services.rfq_poller import run_poller

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
logging.basicConfig(level=logging.INFO)

logger = logging.getLogger("fieldbot.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await run_upgrade(conn)

    poller_task = None
    if settings.imap_enabled:
        poller_task = asyncio.create_task(run_poller())
    else:
        logger.info("IMAP not configured — RFQ inbox poller disabled (procurement uses simulated quotes).")

    yield

    if poller_task:
        poller_task.cancel()
        try:
            await poller_task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="FieldBot", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5173",
        "https://d7fc-103-78-33-50.ngrok-free.app",
    ],
    allow_origin_regex=r"^https://[a-zA-Z0-9-]+\.ngrok-free\.app$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static/uploads", StaticFiles(directory="uploads"), name="uploads")

app.include_router(projects.router)
app.include_router(vendors.router)
app.include_router(inspections.router)
app.include_router(invoices.router)
app.include_router(purchase_orders.router)
app.include_router(events.router)
app.include_router(analytics.router)
app.include_router(webhook.router)

# ARD §5.1 — platform layer (feasibility, quotes, chat, voice, components, PO, overview)
app.include_router(uploads.router)
app.include_router(quotes.router)
app.include_router(feasibility.router)
app.include_router(components.router)
app.include_router(chat.router)
app.include_router(voice.router)
app.include_router(overview.router)
app.include_router(po.router)


@app.get("/")
async def root():
    return {"status": "ok", "service": "FieldBot backend"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000)

