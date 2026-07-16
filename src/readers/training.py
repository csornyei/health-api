from datetime import date, datetime, timezone
from statistics import mean

from influxdb_client_3 import InfluxDBClient3

from src.readers.common import daily_metric, query, ts, ts_end
from src.summary_schemas import (ActivityMetric, HrRecoveryPoint, Training,
                                 WorkoutOut)


def _activity_metric(daily: list[float | None]) -> ActivityMetric:
    populated = [v for v in daily if v is not None]
    total = int(sum(populated))
    avg = int(mean(populated)) if populated else 0
    return ActivityMetric(daily=daily, total=total, avg=avg)


def _read_hr_recovery(
    client: InfluxDBClient3,
    period_start: date,
    period_end: date,
) -> dict[str, list[HrRecoveryPoint]]:
    rows = query(
        client,
        """
        SELECT time, workout_id, "min", "avg", "max"
        FROM "heart_rate_recovery"
        WHERE time >= $start AND time <= $end
        ORDER BY workout_id, time
        """,
        {"start": ts(period_start), "end": ts_end(period_end)},
    )
    result: dict[str, list[HrRecoveryPoint]] = {}
    for row in rows:
        wid = row.get("workout_id")
        if not wid:
            continue
        row_time = row["time"]
        if isinstance(row_time, datetime):
            row_time = row_time.astimezone(timezone.utc).isoformat()
        result.setdefault(wid, []).append(
            HrRecoveryPoint(
                time=str(row_time),
                min_bpm=int(row["min"]),
                avg_bpm=int(row["avg"]),
                max_bpm=int(row["max"]),
            )
        )
    return result


def read_training(
    client: InfluxDBClient3,
    period_start: date,
    period_end: date,
    n: int,
) -> tuple[Training, list[float | None], list[float | None]]:
    active_daily = daily_metric(
        client, "active_energy", "qty", "SUM", period_start, period_end, n
    )
    exercise_daily = daily_metric(
        client, "apple_exercise_time", "qty", "SUM", period_start, period_end, n
    )
    step_daily = daily_metric(
        client, "step_count", "qty", "SUM", period_start, period_end, n
    )
    dist_daily = daily_metric(
        client, "walking_running_distance", "qty", "SUM", period_start, period_end, n
    )

    total_distance = round(sum(v for v in dist_daily if v is not None), 2)

    workout_rows = query(
        client,
        """
        SELECT time AS start_ts, end_ts, id, type, duration_s,
               distance_km, hr_avg_bpm, hr_max_bpm, active_energy
        FROM "workout"
        WHERE time >= $start AND time <= $end
        ORDER BY time
        """,
        {"start": ts(period_start), "end": ts_end(period_end)},
    )
    hr_recovery_by_workout = _read_hr_recovery(client, period_start, period_end)
    workouts: list[WorkoutOut] = []
    for row in workout_rows:
        start_ts: datetime = row["start_ts"]
        if not isinstance(start_ts, datetime):
            start_ts = datetime.fromisoformat(str(start_ts)).astimezone(timezone.utc)
        else:
            start_ts = start_ts.astimezone(timezone.utc)
        dist = row.get("distance_km")
        workout_id = row.get("id")
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
                hr_recovery=hr_recovery_by_workout.get(workout_id, [])
                if workout_id
                else [],
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
