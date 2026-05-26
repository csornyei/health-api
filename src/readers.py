import calendar
from datetime import date, datetime, timedelta, timezone
from statistics import mean

from influxdb_client_3 import InfluxDBClient3

from src.summary_schemas import (
    ActivityMetric,
    DailyMetric,
    Energy,
    Fitness,
    Recovery,
    SleepNight,
    SleepSummary,
    Training,
    TrendMetric,
    WorkoutOut,
    WristTemp,
)


# ── Helpers ────────────────────────────────────────────────────────────────────


def _query(client: InfluxDBClient3, sql: str, params: dict | None = None) -> list[dict]:
    table = client.query(sql, language="sql", query_parameters=params or {})
    if table is None or len(table) == 0:
        return []
    return table.to_pylist()


def _ts(d: date) -> str:
    """Convert a date to a UTC ISO timestamp string for InfluxDB queries."""
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ts_end(d: date) -> str:
    return datetime(d.year, d.month, d.day, 23, 59, 59, tzinfo=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _align_daily(day_map: dict[date, float | None], period_start: date, n: int) -> list[float | None]:
    return [day_map.get(period_start + timedelta(days=i)) for i in range(n)]


def _avg(values: list[float | None]) -> float | None:
    populated = [v for v in values if v is not None]
    return round(mean(populated), 2) if populated else None


def _row_date(row: dict, key: str) -> date:
    """Extract a date from a pyarrow row value (may be datetime or date)."""
    val = row[key]
    if isinstance(val, datetime):
        return val.astimezone(timezone.utc).date()
    return val


TREND_WINDOW = {"week": 3, "twoweeks": 5, "month": 10}


def _calc_trend(
    daily: list[float | None],
    summary_type: str,
    threshold: float,
    higher_is_better: bool = False,
) -> str:
    w = TREND_WINDOW.get(summary_type, 3)
    early = [v for v in daily[:w] if v is not None]
    late = [v for v in daily[-w:] if v is not None]
    if not early or not late:
        return "stable"
    delta = mean(late) - mean(early)
    if abs(delta) < threshold:
        return "stable"
    improving = delta > 0 if higher_is_better else delta < 0
    return "improving" if improving else "worsening"


def _daily_metric(
    client: InfluxDBClient3,
    measurement: str,
    field: str,
    agg: str,
    period_start: date,
    period_end: date,
    n: int,
) -> list[float | None]:
    """Generic daily aggregation query returning a length-N daily array."""
    rows = _query(
        client,
        f"""
        SELECT DATE_TRUNC('day', time) AS day, {agg}("{field}") AS value
        FROM "{measurement}"
        WHERE time >= $start AND time <= $end
        GROUP BY day
        ORDER BY day
        """,
        {"start": _ts(period_start), "end": _ts_end(period_end)},
    )
    day_map: dict[date, float] = {}
    for row in rows:
        d = _row_date(row, "day")
        if row["value"] is not None:
            day_map[d] = round(float(row["value"]), 4)
    return _align_daily(day_map, period_start, n)


# ── Activity ───────────────────────────────────────────────────────────────────


def _activity_metric(daily: list[float | None]) -> ActivityMetric:
    populated = [v for v in daily if v is not None]
    total = int(sum(populated))
    avg = int(mean(populated)) if populated else 0
    return ActivityMetric(daily=daily, total=total, avg=avg)


def read_training(
    client: InfluxDBClient3,
    period_start: date,
    period_end: date,
    n: int,
) -> tuple[Training, list[float | None], list[float | None]]:
    active_daily = _daily_metric(client, "active_energy", "qty", "SUM", period_start, period_end, n)
    exercise_daily = _daily_metric(client, "apple_exercise_time", "qty", "SUM", period_start, period_end, n)
    step_daily = _daily_metric(client, "step_count", "qty", "SUM", period_start, period_end, n)
    dist_daily = _daily_metric(client, "walking_running_distance", "qty", "SUM", period_start, period_end, n)

    total_distance = round(sum(v for v in dist_daily if v is not None), 2)

    workout_rows = _query(
        client,
        """
        SELECT time AS start_ts, end_ts, type, duration_s,
               distance_km, hr_avg_bpm, hr_max_bpm, active_energy
        FROM "workout"
        WHERE time >= $start AND time <= $end
        ORDER BY time
        """,
        {"start": _ts(period_start), "end": _ts_end(period_end)},
    )
    workouts: list[WorkoutOut] = []
    for row in workout_rows:
        start_ts: datetime = row["start_ts"]
        if not isinstance(start_ts, datetime):
            start_ts = datetime.fromisoformat(str(start_ts)).astimezone(timezone.utc)
        else:
            start_ts = start_ts.astimezone(timezone.utc)
        dist = row.get("distance_km")
        workouts.append(
            WorkoutOut(
                type=row["type"],
                date=start_ts.date().isoformat(),
                start_time=start_ts.strftime("%H:%M"),
                duration_min=int((row["duration_s"] or 0) // 60),
                distance_km=round(float(dist), 2) if dist else None,
                avg_hr_bpm=int(row["hr_avg_bpm"]) if row.get("hr_avg_bpm") else None,
                max_hr_bpm=int(row["hr_max_bpm"]) if row.get("hr_max_bpm") else None,
                active_kcal=int(row.get("active_energy") or 0),
            )
        )

    training = Training(
        workouts=workouts,
        active_kcal=_activity_metric(active_daily),
        exercise_min=_activity_metric(exercise_daily),
        steps=_activity_metric(step_daily),
        total_distance_km=total_distance,
    )
    return training, active_daily, dist_daily


def read_energy(
    client: InfluxDBClient3,
    active_daily: list[float | None],
    period_start: date,
    period_end: date,
    n: int,
) -> Energy:
    basal_daily = _daily_metric(client, "basal_energy_burned", "qty", "SUM", period_start, period_end, n)
    tdee_daily: list[float | None] = [
        round(a + b, 2) if a is not None and b is not None else None
        for a, b in zip(active_daily, basal_daily)
    ]
    populated_tdee = [v for v in tdee_daily if v is not None]
    avg_tdee = int(mean(populated_tdee)) if populated_tdee else None
    return Energy(
        active_kcal_daily=active_daily,
        basal_kcal_daily=basal_daily,
        tdee_daily=tdee_daily,
        avg_tdee=avg_tdee,
    )


# ── Recovery ───────────────────────────────────────────────────────────────────


def read_recovery(
    client: InfluxDBClient3,
    summary_type: str,
    period_start: date,
    period_end: date,
    n: int,
) -> Recovery:
    rhr_daily = _daily_metric(client, "resting_heart_rate", "qty", "AVG", period_start, period_end, n)
    hrv_daily = _daily_metric(client, "heart_rate_variability", "qty", "AVG", period_start, period_end, n)
    resp_daily = _daily_metric(client, "respiratory_rate", "qty", "AVG", period_start, period_end, n)
    spo2_daily = _daily_metric(client, "blood_oxygen_saturation", "qty", "AVG", period_start, period_end, n)
    breath_daily = _daily_metric(client, "breathing_disturbances", "qty", "AVG", period_start, period_end, n)

    # Wrist temp — current period
    wrist_daily = _daily_metric(
        client, "apple_sleeping_wrist_temperature", "qty", "AVG", period_start, period_end, n
    )
    # Baseline = 30 days before period_start
    baseline_start = period_start - timedelta(days=30)
    baseline_rows = _query(
        client,
        'SELECT AVG("qty") AS baseline FROM "apple_sleeping_wrist_temperature" WHERE time >= $start AND time < $end',
        {"start": _ts(baseline_start), "end": _ts(period_start)},
    )
    baseline: float | None = None
    if baseline_rows and baseline_rows[0].get("baseline") is not None:
        baseline = round(float(baseline_rows[0]["baseline"]), 4)
    deviations: list[float | None] = [
        round(v - baseline, 4) if v is not None and baseline is not None else None
        for v in wrist_daily
    ]

    return Recovery(
        resting_hr=TrendMetric(
            daily=rhr_daily,
            avg=_avg(rhr_daily),
            trend=_calc_trend(rhr_daily, summary_type, threshold=3.0, higher_is_better=False),
        ),
        hrv=TrendMetric(
            daily=hrv_daily,
            avg=_avg(hrv_daily),
            trend=_calc_trend(hrv_daily, summary_type, threshold=5.0, higher_is_better=True),
        ),
        respiratory_rate=DailyMetric(daily=resp_daily, avg=_avg(resp_daily)),
        spo2=DailyMetric(daily=spo2_daily, avg=_avg(spo2_daily)),
        breathing_disturbances=DailyMetric(daily=breath_daily, avg=_avg(breath_daily)),
        wrist_temp=WristTemp(daily=wrist_daily, baseline=baseline, deviations=deviations),
    )


# ── Sleep ──────────────────────────────────────────────────────────────────────


def read_sleep(
    client: InfluxDBClient3,
    period_start: date,
    period_end: date,
) -> tuple[list[SleepNight], SleepSummary]:
    rows = _query(
        client,
        """
        SELECT time AS sleep_start_ts, sleep_end_ts,
               total_sleep, core, deep, rem, awake, "inBed"
        FROM "sleep_analysis"
        WHERE time >= $start AND time <= $end AND source LIKE '%Watch%'
        ORDER BY time
        """,
        {"start": _ts(period_start), "end": _ts_end(period_end)},
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
            end_dt = start_ts  # fallback; shouldn't happen

        total = float(row.get("total_sleep") or 0)
        deep = float(row.get("deep") or 0)
        rem = float(row.get("rem") or 0)
        core = float(row.get("core") or 0)
        awake = float(row.get("awake") or 0)
        in_bed = float(row.get("inBed") or 0) or (deep + rem + core + awake)
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


# ── Fitness ────────────────────────────────────────────────────────────────────


def read_fitness(
    client: InfluxDBClient3,
    period_start: date,
    period_end: date,
) -> Fitness:
    current_rows = _query(
        client,
        'SELECT qty FROM "vo2_max" WHERE time <= $end ORDER BY time DESC LIMIT 1',
        {"end": _ts_end(period_end)},
    )
    prior_rows = _query(
        client,
        'SELECT qty FROM "vo2_max" WHERE time < $start ORDER BY time DESC LIMIT 1',
        {"start": _ts(period_start)},
    )

    current = float(current_rows[0]["qty"]) if current_rows else None
    prior = float(prior_rows[0]["qty"]) if prior_rows else None
    delta = round(current - prior, 2) if current is not None and prior is not None else None

    return Fitness(vo2_max_current=current, vo2_max_prior=prior, vo2_max_delta=delta)