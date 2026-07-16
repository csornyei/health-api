from datetime import date, datetime, timezone
from statistics import mean

from influxdb_client_3 import InfluxDBClient3

from src.readers.common import query, ts, ts_end
from src.summary_schemas import SleepNight, SleepSummary


def read_sleep(
    client: InfluxDBClient3,
    period_start: date,
    period_end: date,
) -> tuple[list[SleepNight], SleepSummary]:
    rows = query(
        client,
        """
        SELECT time AS sleep_start_ts, sleep_end_ts,
               total_sleep, core, deep, rem, awake
        FROM "sleep_analysis"
        WHERE time >= $start AND time <= $end
        ORDER BY time
        """,
        {"start": ts(period_start), "end": ts_end(period_end)},
    )

    nights: list[SleepNight] = []
    for row in rows:
        start_ts: datetime = row["sleep_start_ts"]
        if not isinstance(start_ts, datetime):
            start_ts = datetime.fromisoformat(str(start_ts)).astimezone(timezone.utc)
        else:
            start_ts = start_ts.astimezone(timezone.utc)

        end_ts_raw = row.get("sleep_end_ts")
        if end_ts_raw is not None:
            end_dt = datetime.fromtimestamp(int(end_ts_raw), tz=timezone.utc)
        else:
            end_dt = start_ts

        total = float(row.get("total_sleep") or 0)
        deep = float(row.get("deep") or 0)
        rem = float(row.get("rem") or 0)
        core = float(row.get("core") or 0)
        awake = float(row.get("awake") or 0)
        in_bed = deep + rem + core + awake
        efficiency = round(total / in_bed * 100, 1) if in_bed else None

        nights.append(
            SleepNight(
                date=start_ts.date().isoformat(),
                total_h=round(total, 2),
                deep_h=round(deep, 2),
                rem_h=round(rem, 2),
                core_h=round(core, 2),
                awake_h=round(awake, 2),
                efficiency_pct=efficiency,
                sleep_start=start_ts.strftime("%H:%M"),
                sleep_end=end_dt.strftime("%H:%M"),
            )
        )

    def _safe_avg(vals: list[float | None]) -> float | None:
        populated = [v for v in vals if v is not None]
        return round(mean(populated), 2) if populated else None

    summary = SleepSummary(
        avg_total_h=_safe_avg([n.total_h for n in nights]),
        avg_deep_h=_safe_avg([n.deep_h for n in nights]),
        avg_rem_h=_safe_avg([n.rem_h for n in nights]),
        avg_efficiency_pct=_safe_avg([n.efficiency_pct for n in nights]),
    )
    return nights, summary
