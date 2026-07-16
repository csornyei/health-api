from typing import Any


def validation_errors(errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "loc": [str(part) for part in error.get("loc", [])],
            "msg": error.get("msg", "Invalid value"),
            "type": error.get("type", "value_error"),
        }
        for error in errors
    ]
