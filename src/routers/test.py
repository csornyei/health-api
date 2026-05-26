import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Request

router = APIRouter(prefix="/test")

_TEST_DATA_FILE = Path("test_data.json")


@router.post("/")
async def test_endpoint(request: Request) -> dict:
    body = await request.body()
    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, ValueError):
        payload = body.decode()

    records = []
    if _TEST_DATA_FILE.exists():
        records = json.loads(_TEST_DATA_FILE.read_text())

    records.append({"received_at": datetime.now(timezone.utc).isoformat(), "payload": payload})
    _TEST_DATA_FILE.write_text(json.dumps(records, indent=2))

    return {"status": "ok"}
