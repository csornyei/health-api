from influxdb_client_3 import InfluxDBClient3, Point
from opentelemetry import trace
from opentelemetry.trace import StatusCode

from src.logger import logger
from src.schemas import Workout
from src.writers.common import parse_ts

_tracer = trace.get_tracer(__name__)


def write_workouts(client: InfluxDBClient3, workouts: list[Workout]) -> None:
    points = []
    for workout in workouts:
        try:
            points.extend(workout_points(workout))
        except Exception as exc:
            logger.error(
                "failed to build workout points",
                workout_id=workout.id,
                workout_name=workout.name,
                workout_start=workout.start,
                exc_info=exc,
            )
            raise
    with _tracer.start_as_current_span("influxdb.write_workouts") as span:
        span.set_attribute("db.workouts_count", len(workouts))
        span.set_attribute("db.points_count", len(points))
        try:
            if points:
                client.write(record=points)
        except Exception as exc:
            span.record_exception(exc)
            span.set_status(StatusCode.ERROR, str(exc))
            logger.error(
                "failed to write workout points",
                workouts_count=len(workouts),
                points_count=len(points),
                workout_ids=[workout.id for workout in workouts[:10]],
                exc_info=exc,
            )
            raise
    logger.info(
        "workouts written", workouts_count=len(workouts), points_written=len(points)
    )


def workout_points(workout: Workout) -> list[Point]:
    start_ts = parse_ts(workout.start)
    end_ts = parse_ts(workout.end)

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
        hr_min = (
            min(p.Min for p in workout.heartRateData) if workout.heartRateData else None
        )

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

    for point in workout.heartRateData:
        points.append(
            Point("heart_rate")
            .tag("workout_id", workout.id)
            .tag("units", point.units)
            .field("min", point.Min)
            .field("avg", point.Avg)
            .field("max", point.Max)
            .time(parse_ts(point.date))
        )

    for point in workout.heartRateRecovery:
        points.append(
            Point("heart_rate_recovery")
            .tag("workout_id", workout.id)
            .tag("units", point.units)
            .field("min", point.Min)
            .field("avg", point.Avg)
            .field("max", point.Max)
            .time(parse_ts(point.date))
        )

    for point in workout.activeEnergy:
        points.append(
            Point("active_energy")
            .tag("workout_id", workout.id)
            .tag("units", point.units)
            .field("qty", point.qty)
            .time(parse_ts(point.date))
        )

    for point in workout.walkingAndRunningDistance:
        points.append(
            Point("distance")
            .tag("workout_id", workout.id)
            .tag("units", point.units)
            .field("qty", point.qty)
            .time(parse_ts(point.date))
        )

    for point in workout.stepCount:
        points.append(
            Point("steps")
            .tag("workout_id", workout.id)
            .tag("units", point.units)
            .field("qty", point.qty)
            .time(parse_ts(point.date))
        )

    return points


_workout_points = workout_points
