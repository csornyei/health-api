from influxdb_client_3 import Point

from src.schemas import SleepDataPoint
from src.writers.common import parse_ts


def sleep_point(name: str, point: SleepDataPoint) -> Point:
    sleep_start = parse_ts(point.sleepStart)
    sleep_end = parse_ts(point.sleepEnd)
    duration_hours = (sleep_end - sleep_start).total_seconds() / 3600
    return (
        Point(name)
        .field("duration_hours", round(duration_hours, 4))
        .field("sleep_end_ts", int(sleep_end.timestamp()))
        .field("total_sleep", point.totalSleep)
        .field("core", point.core)
        .field("deep", point.deep)
        .field("rem", point.rem)
        .field("awake", point.awake)
        .field("asleep", point.asleep)
        .time(sleep_start)
    )
