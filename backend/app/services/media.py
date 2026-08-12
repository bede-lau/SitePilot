import httpx

from app.config import settings


async def download_telegram_media(file_id: str) -> bytes:
    """Resolve a Telegram file_id to its bytes.

    Telegram is a two-step download: getFile returns a short-lived file_path,
    then the file is fetched from the file CDN under the same bot token."""
    async with httpx.AsyncClient(timeout=20) as client:
        meta = await client.get(
            f"{settings.telegram_api_base}/getFile", params={"file_id": file_id}
        )
        meta.raise_for_status()
        file_path = meta.json()["result"]["file_path"]

        resp = await client.get(f"{settings.telegram_file_base}/{file_path}")
        resp.raise_for_status()
        return resp.content
