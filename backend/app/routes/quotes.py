"""ARD §5.1/§5.4 — quote parsing endpoints. Thin HTTP layer over
app.services.quote_ingest, shared with agents/tools.py's parse_supplier_quote
tool so the dashboard drop-zone and the chat tool never drift."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.models import SupplierQuote
from app.schemas import QuoteParseRequest
from app.services.quote_ingest import QuoteIngestError, ingest_quote, serialize_quote

router = APIRouter(prefix="/api/quotes", tags=["quotes"])


@router.post("/parse")
async def parse_quote_endpoint(payload: QuoteParseRequest, db: AsyncSession = Depends(get_db)):
    try:
        quote = await ingest_quote(db, payload.file_id, payload.project_id)
    except QuoteIngestError as exc:
        status_code = 404 if "No uploaded file" in str(exc) else 503
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return serialize_quote(quote)


@router.get("")
async def list_quotes(project_id: int | None = None, db: AsyncSession = Depends(get_db)):
    query = select(SupplierQuote).order_by(SupplierQuote.created_at.desc())
    if project_id is not None:
        query = query.where(SupplierQuote.project_id == project_id)
    quotes = (await db.execute(query)).scalars().all()
    out = []
    for q in quotes:
        await db.refresh(q, attribute_names=["line_items"])
        out.append(serialize_quote(q))
    return out


@router.get("/{quote_id}")
async def get_quote(quote_id: int, db: AsyncSession = Depends(get_db)):
    quote = await db.get(SupplierQuote, quote_id)
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    await db.refresh(quote, attribute_names=["line_items"])
    return serialize_quote(quote)
