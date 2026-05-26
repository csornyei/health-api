import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from src.logger import logger

router = APIRouter(prefix="/test")

_TEST_DATA_FILE = Path("test_data.json")


@router.post("/", tags=["test"])
async def test_endpoint(request: Request) -> dict:
    body = await request.body()
    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, ValueError):
        payload = body.decode()

    records = []
    if _TEST_DATA_FILE.exists():
        try:
            records = json.loads(_TEST_DATA_FILE.read_text())
        except (json.JSONDecodeError, ValueError) as exc:
            logger.error("test data file is corrupt, starting fresh", path=str(_TEST_DATA_FILE), exc_info=exc)

    records.append({"received_at": datetime.now(timezone.utc).isoformat(), "payload": payload})
    try:
        _TEST_DATA_FILE.write_text(json.dumps(records, indent=2))
    except OSError as exc:
        logger.error("failed to write test data file", path=str(_TEST_DATA_FILE), exc_info=exc)
        raise HTTPException(status_code=500, detail="Failed to persist test data") from exc

    logger.info("test payload recorded", path=str(_TEST_DATA_FILE), total_records=len(records))
    return {"status": "ok"}
