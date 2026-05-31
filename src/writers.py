from datetime import datetime, timezone

from influxdb_client_3 import InfluxDBClient3, Point

from src.logger import logger
from src.schemas import HeartRateMetricPoint, Metric, QuantityDataPoint, SleepDataPoint, Workout


def write_metrics(client: InfluxDBClient3, metrics: list[Metric]) -> None:
    points = []
    for metric in metrics:
        for point in metric.data:
            if isinstance(point, SleepDataPoint):
                points.append(_sleep_point(metric.name, point))
            elif isinstance(point, HeartRateMetricPoint):
                points.append(_heart_rate_point(metric.name, metric.units, point))
            elif isinstance(point, QuantityDataPoint):
                points.append(_quantity_point(metric.name, metric.units, point))
    client.write(record=points)
    logger.info("metrics written", metrics_count=len(metrics), points_written=len(points))


def write_workouts(client: InfluxDBClient3, workouts: list[Workout]) -> None:
    points = []
    for workout in workouts:
        points.extend(_workout_points(workout))
    if points:
        client.write(record=points)
    logger.info("workouts written", workouts_count=len(workouts), points_written=len(points))


def _parse_ts(date_str: str) -> datetime:
    return datetime.fromisoformat(date_str).astimezone(timezone.utc)


def _quantity_point(name: str, units: str | None, point: QuantityDataPoint) -> Point:
    return (
        Point(name)
        .tag("units", units or "")
        .field("qty", point.qty)
        .time(_parse_ts(point.date))
    )


def _heart_rate_point(name: str, units: str | None, point: HeartRateMetricPoint) -> Point:
    return (
        Point(name)
        .tag("units", units or "")
        .field("min", point.Min)
        .field("avg", point.Avg)
        .field("max", point.Max)
        .time(_parse_ts(point.date))
    )


def _sleep_point(name: str, point: SleepDataPoint) -> Point:
    sleep_start = _parse_ts(point.sleepStart)
    sleep_end = _parse_ts(point.sleepEnd)
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


def _workout_points(workout: Workout) -> list[Point]:
    start_ts = _parse_ts(workout.start)
    end_ts = _parse_ts(workout.end)

    # Resolve heart rate summary — prefer the heartRate object, fall back to flat fields / raw data
    hr_avg: float | None = None
    hr_min: float | None = None
    hr_max: float | None = None
    if workout.heartRate:
        hr_avg = workout.heartRate.avg.qty
        hr_min = workout.heartRate.min.qty
        hr_max = workout.heartRate.max.qty
    else:
        hr_avg = workout.avgHeartRate.qty if workout.avgHeartRate else None
        hr_max = workout.maxHeartRate.qty if workout.maxHeartRate else None
        hr_min = min(p.Min for p in workout.heartRateData) if workout.heartRateData else None


    summary = (
        Point("workout")
        .tag("id", workout.id)
        .tag("type", workout.name)
        .field("end_ts", int(end_ts.timestamp()))
        .field("duration_s", int(workout.duration))
        .field("distance_km", workout.distance.qty)
        .field("speed_kmh", workout.speed.qty)
        .field("active_energy", workout.activeEnergyBurned.qty)
        .field("step_cadence", workout.stepCadence.qty)
        .time(start_ts)
    )
    if hr_avg is not None:
        summary = summary.field("hr_avg_bpm", hr_avg)
    if hr_min is not None:
        summary = summary.field("hr_min_bpm", int(hr_min))
    if hr_max is not None:
        summary = summary.field("hr_max_bpm", int(hr_max))
    points: list[Point] = [summary]

    for p in workout.heartRateData:
        points.append(
            Point("heart_rate")
            .tag("workout_id", workout.id)
            .tag("units", p.units)
            .field("min", p.Min)
            .field("avg", p.Avg)
            .field("max", p.Max)
            .time(_parse_ts(p.date))
        )

    for p in workout.heartRateRecovery:
        points.append(
            Point("heart_rate_recovery")
            .tag("workout_id", workout.id)
            .tag("units", p.units)
            .field("min", p.Min)
            .field("avg", p.Avg)
            .field("max", p.Max)
            .time(_parse_ts(p.date))
        )

    for p in workout.activeEnergy:
        points.append(
            Point("active_energy")
            .tag("workout_id", workout.id)
            .tag("units", p.units)
            .field("qty", p.qty)
            .time(_parse_ts(p.date))
        )

    for p in workout.walkingAndRunningDistance:
        points.append(
            Point("distance")
            .tag("workout_id", workout.id)
            .tag("units", p.units)
            .field("qty", p.qty)
            .time(_parse_ts(p.date))
        )

    for p in workout.stepCount:
        points.append(
            Point("steps")
            .tag("workout_id", workout.id)
            .tag("units", p.units)
            .field("qty", p.qty)
            .time(_parse_ts(p.date))
        )

    return points
