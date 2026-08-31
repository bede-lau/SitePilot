"""PDF/image → page-image + text-layer extraction for the quote parser.

Renders PDF pages to PNG bytes for the vision model and pulls the (best-effort)
text layer as an extra hint. Also normalises a directly-photographed quote
(JPEG/PNG) through the same size-capping pipeline so `agents/quote_parser.py`
can treat both inputs identically. Pure I/O-free-of-network helpers — no DB,
no LLM calls here.
"""
import io

import pypdfium2 as pdfium
from PIL import Image

PDF_MAGIC = b"%PDF-"

RENDER_DPI = 150  # before downscale — keeps small table text legible
DEFAULT_MAX_PAGES = 4
DEFAULT_MAX_PX = 1600  # long-edge cap so vision token usage stays sane


def is_pdf(data: bytes) -> bool:
    """Magic-byte sniff so the same upload path accepts a PDF or a photographed quote."""
    return data[:5] == PDF_MAGIC


def page_count(data: bytes) -> int:
    pdf = pdfium.PdfDocument(data)
    try:
        return len(pdf)
    finally:
        pdf.close()


def _downscale(image: Image.Image, max_px: int) -> Image.Image:
    width, height = image.size
    longest = max(width, height)
    if longest <= max_px:
        return image
    ratio = max_px / longest
    new_size = (max(1, round(width * ratio)), max(1, round(height * ratio)))
    return image.resize(new_size, Image.LANCZOS)


def _to_png_bytes(image: Image.Image) -> bytes:
    if image.mode not in ("RGB", "L"):
        image = image.convert("RGB")
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def render_pdf_pages(
    data: bytes, max_pages: int = DEFAULT_MAX_PAGES, max_px: int = DEFAULT_MAX_PX
) -> list[bytes]:
    """Render up to `max_pages` pages to PNG bytes, long edge capped at `max_px`.

    Renders at ~150 DPI first (RENDER_DPI) so small table text stays legible,
    then downsamples to `max_px` — this keeps the vision call's token usage
    reasonable without losing line-item readability.
    """
    pdf = pdfium.PdfDocument(data)
    try:
        scale = RENDER_DPI / 72
        pages_out: list[bytes] = []
        for i in range(min(len(pdf), max_pages)):
            page = pdf[i]
            try:
                bitmap = page.render(scale=scale)
                try:
                    image = bitmap.to_pil()
                finally:
                    bitmap.close()
                image = _downscale(image, max_px)
                pages_out.append(_to_png_bytes(image))
            finally:
                page.close()
        return pages_out
    finally:
        pdf.close()


def extract_pdf_text(data: bytes) -> str:
    """Best-effort text-layer extraction. Empty string for scanned/image-only PDFs —
    that's fine, it's used only as an extra hint alongside the page images."""
    try:
        pdf = pdfium.PdfDocument(data)
    except Exception:
        return ""
    try:
        chunks: list[str] = []
        for i in range(len(pdf)):
            page = pdf[i]
            try:
                textpage = page.get_textpage()
                try:
                    chunks.append(textpage.get_text_range())
                finally:
                    textpage.close()
            finally:
                page.close()
        return "\n".join(c for c in chunks if c).strip()
    except Exception:
        return ""
    finally:
        pdf.close()


def normalise_image(data: bytes, max_px: int = DEFAULT_MAX_PX) -> bytes:
    """Run a photographed quote (JPEG/PNG/etc) through the same PNG + size-cap
    pipeline as a rendered PDF page, so the parser's vision call sees one shape."""
    image = Image.open(io.BytesIO(data))
    image.load()
    image = _downscale(image, max_px)
    return _to_png_bytes(image)
