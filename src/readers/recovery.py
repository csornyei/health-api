from datetime import date, timedelta
from statistics import mean

from influxdb_client_3 import InfluxDBClient3

from src.readers.common import avg, daily_metric, query, ts
from src.summary_schemas import DailyMetric, Recovery, TrendMetric, WristTemp

TREND_WINDOW = {"week": 3, "twoweeks": 5, "thirtydays": 10, "month": 10}


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


def read_recovery(
    client: InfluxDBClient3,
    summary_type: str,
    period_start: date,
    period_end: date,
    n: int,
) -> Recovery:
    rhr_daily = daily_metric(
        client, "resting_heart_rate", "qty", "AVG", period_start, period_end, n
    )
    hrv_daily = daily_metric(
        client, "heart_rate_variability", "qty", "AVG", period_start, period_end, n
    )
    resp_daily = daily_metric(
        client, "respiratory_rate", "qty", "AVG", period_start, period_end, n
    )
    spo2_daily = daily_metric(
        client, "blood_oxygen_saturation", "qty", "AVG", period_start, period_end, n
    )
    breath_daily = daily_metric(
        client, "breathing_disturbances", "qty", "AVG", period_start, period_end, n
    )

    wrist_daily = daily_metric(
        client,
        "apple_sleeping_wrist_temperature",
        "qty",
        "AVG",
        period_start,
        period_end,
        n,
    )
    baseline_start = period_start - timedelta(days=30)
    baseline_rows = query(
        client,
        'SELECT AVG("qty") AS baseline FROM "apple_sleeping_wrist_temperature" WHERE time >= $start AND time < $end',
        {"start": ts(baseline_start), "end": ts(period_start)},
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
            avg=avg(rhr_daily),
            trend=_calc_trend(
                rhr_daily, summary_type, threshold=3.0, higher_is_better=False
            ),
        ),
        hrv=TrendMetric(
            daily=hrv_daily,
            avg=avg(hrv_daily),
            trend=_calc_trend(
                hrv_daily, summary_type, threshold=5.0, higher_is_better=True
            ),
        ),
        respiratory_rate=DailyMetric(daily=resp_daily, avg=avg(resp_daily)),
        spo2=DailyMetric(daily=spo2_daily, avg=avg(spo2_daily)),
        breathing_disturbances=DailyMetric(daily=breath_daily, avg=avg(breath_daily)),
        wrist_temp=WristTemp(
            daily=wrist_daily, baseline=baseline, deviations=deviations
        ),
    )
