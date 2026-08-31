"""ARD §5.1 — POST /api/po/generate. Thin HTTP layer over
app.services.po_engine, shared with agents/tools.py's generate_po_package
tool."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas import PoGenerateRequest
from app.services.po_engine import PoGenerateError, generate_po

router = APIRouter(prefix="/api/po", tags=["po"])


@router.post("/generate")
async def generate_po_endpoint(payload: PoGenerateRequest, db: AsyncSession = Depends(get_db)):
    try:
        return await generate_po(
            db,
            feasibility_run_id=payload.feasibility_run_id,
            vendor_id=payload.vendor_id,
            notify_telegram=payload.notify_telegram,
        )
    except PoGenerateError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
