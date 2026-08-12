import asyncio
import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import Base, engine
from app.models import models  # noqa: F401  (ensures models register on Base.metadata)
from app.routes import analytics, events, inspections, invoices, projects, purchase_orders, vendors, webhook
from app.services.rfq_poller import run_poller

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
logging.basicConfig(level=logging.INFO)

logger = logging.getLogger("fieldbot.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

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
    allow_origins=["http://localhost:5173"],
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


@app.get("/")
async def root():
    return {"status": "ok", "service": "FieldBot backend"}
