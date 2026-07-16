from datetime import datetime, timezone


def parse_ts(date_str: str) -> datetime:
    return datetime.fromisoformat(date_str).astimezone(timezone.utc)
