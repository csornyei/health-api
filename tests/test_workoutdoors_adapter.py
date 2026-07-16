from src.adapters.workoutdoors import WorkoutParseError, parse_workouts_payload


def _value(qty: float, units: str) -> dict:
    return {"qty": qty, "units": units}


def test_parse_existing_workouts_export_keeps_health_auto_export_format() -> None:
    payload = {
        "data": {
            "workouts": [
                {
                    "id": "existing-1",
                    "name": "Run",
                    "start": "2026-06-16T17:35:37+02:00",
                    "end": "2026-06-16T18:35:39+02:00",
                    "duration": 3602.0,
                    "distance": _value(10, "km"),
                    "speed": _value(10, "km/hr"),
                    "stepCadence": _value(170, "spm"),
                    "activeEnergyBurned": _value(600, "kcal"),
                    "activeEnergy": [],
                    "walkingAndRunningDistance": [],
                    "stepCount": [],
                }
            ]
        }
    }

    parsed = parse_workouts_payload(payload)

    assert parsed.payload_format == "health_auto_export"
    assert parsed.export.data.workouts[0].id == "existing-1"


def test_parse_workoutdoors_payload_defaults_missing_series_and_ignores_extras() -> (
    None
):
    payload = {
        "data": {
            "workouts": [
                {
                    "id": "workoutdoors-1",
                    "name": "Hiking",
                    "start": "2026-06-13 12:51:35 +0200",
                    "end": "2026-06-13 20:53:35 +0200",
                    "duration": 28920.0,
                    "distance": _value(32.1, "km"),
                    "speed": _value(4.1, "km/hr"),
                    "stepCadence": _value(110, "spm"),
                    "activeEnergyBurned": _value(1500, "kcal"),
                    "activeEnergy": [
                        {
                            "source": "Apple Watch",
                            "date": "2026-06-13 12:51:35 +0200",
                            "qty": 5.6,
                            "units": "kcal",
                        }
                    ],
                    "stepCount": [],
                    "route": [{"latitude": 52.4, "longitude": 4.9}],
                    "totalEnergy": _value(1800, "kcal"),
                    "temperature": _value(18, "degC"),
                }
            ]
        }
    }

    parsed = parse_workouts_payload(payload)
    workout = parsed.export.data.workouts[0]

    assert parsed.payload_format == "workoutdoors"
    assert workout.id == "workoutdoors-1"
    assert workout.walkingAndRunningDistance == []
    assert workout.activeEnergy[0].qty == 5.6
    assert parsed.ignored_fields == ["route", "temperature", "totalEnergy"]


def test_parse_test_endpoint_record_wrapper() -> None:
    payload = {
        "received_at": "2026-07-16T08:53:03.631766+00:00",
        "payload": {
            "data": {
                "workouts": [
                    {
                        "id": "wrapped-1",
                        "name": "Run",
                        "start": "2026-06-16 17:35:37 +0200",
                        "end": "2026-06-16 18:35:39 +0200",
                        "duration": 3602.0,
                        "distance": _value(10, "km"),
                        "speed": _value(10, "km/hr"),
                        "stepCadence": _value(170, "spm"),
                        "activeEnergyBurned": _value(600, "kcal"),
                        "activeEnergy": [],
                        "stepCount": [],
                    }
                ]
            }
        },
    }

    parsed = parse_workouts_payload(payload)

    assert parsed.payload_format == "workoutdoors"
    assert parsed.export.data.workouts[0].id == "wrapped-1"


def test_parse_unsupported_workout_payload_reports_parser_errors() -> None:
    try:
        parse_workouts_payload({"data": {"workouts": [{"id": "nope"}]}})
    except WorkoutParseError as exc:
        errors = exc.errors
    else:
        raise AssertionError("expected WorkoutParseError")

    assert [error["parser"] for error in errors] == [
        "health_auto_export",
        "workoutdoors",
    ]
    assert errors[0]["errors"]
    assert errors[1]["errors"]
