import os

os.environ.setdefault("INFLUXDB_HOST", "http://localhost:8181")
os.environ.setdefault("INFLUXDB_TOKEN", "test-token")
os.environ.setdefault("INFLUXDB_DATABASE", "test-db")
os.environ.setdefault("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")

from src.routers.test import router as debug_router
from src.validation import validation_errors


def test_test_router_registers_no_trailing_slash_route() -> None:
    paths = {route.path for route in debug_router.routes}

    assert "/test" in paths


def test_validation_errors_are_safe_for_logs_and_responses() -> None:
    errors = validation_errors(
        [
            {
                "loc": ("body", "data", "workouts", 0, "id"),
                "msg": "Field required",
                "type": "missing",
                "input": {"large": "payload"},
            }
        ]
    )

    assert errors == [
        {
            "loc": ["body", "data", "workouts", "0", "id"],
            "msg": "Field required",
            "type": "missing",
        }
    ]
