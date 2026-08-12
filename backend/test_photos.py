import asyncio
import json
from pathlib import Path

from app.services.llm_client import analyze_photo

UPLOADS_DIR = Path(__file__).parent / "uploads"


async def main():
    for path in sorted(UPLOADS_DIR.iterdir()):
        if not path.is_file():
            continue
        image_bytes = path.read_bytes()
        result = await analyze_photo(image_bytes)
        print(f"\n=== {path.name} ===")
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
