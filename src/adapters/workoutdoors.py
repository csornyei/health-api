from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from src.schemas import (HeartRateSummary, ValueWithUnits, Workout,
                         WorkoutHeartRatePoint, WorkoutsData, WorkoutsExport,
                         WorkoutTimeSeriesPoint)
from src.validation import validation_errors

IGNORED_WORKOUTDOORS_FIELDS = {
    "avgSpeed",
    "basalEnergy",
    "elevationUp",
    "humidity",
    "intensity",
    "isIndoor",
    "location",
    "maxSpeed",
    "metadata",
    "route",
    "temperature",
    "totalEnergy",
}


class WorkoutdoorsWorkout(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    name: str
    start: str
    end: str
    duration: float
    distance: ValueWithUnits
    speed: ValueWithUnits
    stepCadence: ValueWithUnits
    activeEnergyBurned: ValueWithUnits
    avgHeartRate: ValueWithUnits | None = None
    maxHeartRate: ValueWithUnits | None = None
    heartRate: HeartRateSummary | None = None
    heartRateData: list[WorkoutHeartRatePoint] = Field(default_factory=list)
    heartRateRecovery: list[WorkoutHeartRatePoint] = Field(default_factory=list)
    activeEnergy: list[WorkoutTimeSeriesPoint] = Field(default_factory=list)
    walkingAndRunningDistance: list[WorkoutTimeSeriesPoint] = Field(
        default_factory=list
    )
    stepCount: list[WorkoutTimeSeriesPoint] = Field(default_factory=list)


class WorkoutdoorsData(BaseModel):
    workouts: list[WorkoutdoorsWorkout]


class WorkoutdoorsExport(BaseModel):
    data: WorkoutdoorsData


class ParsedWorkouts(BaseModel):
    export: WorkoutsExport
    payload_format: str
    ignored_fields: list[str] = []


class WorkoutParseError(ValueError):
    def __init__(self, errors: list[dict[str, Any]]) -> None:
        super().__init__("Unsupported workout payload")
        self.errors = errors


def parse_workouts_payload(payload: Any) -> ParsedWorkouts:
    normalized_payload = _unwrap_test_record(payload)

    try:
        export = WorkoutsExport.model_validate(normalized_payload)
    except ValidationError as existing_exc:
        existing_errors = validation_errors(existing_exc.errors())
    else:
        return ParsedWorkouts(export=export, payload_format="health_auto_export")

    try:
        workoutdoors = WorkoutdoorsExport.model_validate(normalized_payload)
        export = _convert_workoutdoors(workoutdoors)
    except ValidationError as workoutdoors_exc:
        raise WorkoutParseError(
            [
                {
                    "parser": "health_auto_export",
                    "errors": existing_errors,
                },
                {
                    "parser": "workoutdoors",
                    "errors": validation_errors(workoutdoors_exc.errors()),
                },
            ]
        ) from workoutdoors_exc

    return ParsedWorkouts(
        export=export,
        payload_format="workoutdoors",
        ignored_fields=_ignored_fields(normalized_payload),
    )


def _unwrap_test_record(payload: Any) -> Any:
    if isinstance(payload, list) and len(payload) == 1 and isinstance(payload[0], dict):
        return payload[0].get("payload", payload)
    if isinstance(payload, dict) and "payload" in payload and "received_at" in payload:
        return payload["payload"]
    return payload


def _convert_workoutdoors(export: WorkoutdoorsExport) -> WorkoutsExport:
    workouts = [
        Workout(
            id=workout.id,
            name=workout.name,
            start=workout.start,
            end=workout.end,
            duration=workout.duration,
            distance=workout.distance,
            speed=workout.speed,
            stepCadence=workout.stepCadence,
            activeEnergyBurned=workout.activeEnergyBurned,
            avgHeartRate=workout.avgHeartRate,
            maxHeartRate=workout.maxHeartRate,
            heartRate=workout.heartRate,
            heartRateData=workout.heartRateData,
            heartRateRecovery=workout.heartRateRecovery,
            activeEnergy=workout.activeEnergy,
            walkingAndRunningDistance=workout.walkingAndRunningDistance,
            stepCount=workout.stepCount,
        )
        for workout in export.data.workouts
    ]
    return WorkoutsExport(data=WorkoutsData(workouts=workouts))


def _ignored_fields(payload: Any) -> list[str]:
    if not isinstance(payload, dict):
        return []
    workouts = payload.get("data", {}).get("workouts", [])
    ignored: set[str] = set()
    for workout in workouts:
        if isinstance(workout, dict):
            ignored.update(set(workout) & IGNORED_WORKOUTDOORS_FIELDS)
    return sorted(ignored)
