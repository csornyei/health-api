from datetime import date
from types import SimpleNamespace

import pytest

from src.readers import _daily_metric
from src.readers.common import capture_missing_measurements, query


class FakeTable:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    def __len__(self) -> int:
        return len(self._rows)

    def to_pylist(self) -> list[dict]:
        return self._rows


class FakeClient:
    def __init__(self, rows_by_start: dict[str, list[dict]]) -> None:
        self.rows_by_start = rows_by_start
        self.calls: list[dict] = []

    def query(self, sql: str, language: str, query_parameters: dict) -> FakeTable:
        self.calls.append(
            {
                "sql": sql,
                "language": language,
                "query_parameters": query_parameters,
            }
        )
        return FakeTable(self.rows_by_start.get(query_parameters["start"], []))


class FailingClient:
    def __init__(self, error: Exception) -> None:
        self.error = error

    def query(self, sql: str, language: str, query_parameters: dict) -> FakeTable:
        raise self.error


def test_daily_metric_queries_one_day_chunks_and_aligns_results(monkeypatch) -> None:
    client = FakeClient(
        {
            "2026-07-01T00:00:00Z": [{"day": date(2026, 7, 1), "value": 10}],
            "2026-07-03T00:00:00Z": [{"day": date(2026, 7, 3), "value": 30.12345}],
        }
    )
    settings = SimpleNamespace(summary_query_chunk_days=1)
    monkeypatch.setattr("src.readers.common.get_settings", lambda: settings)

    result = _daily_metric(
        client=client,
        measurement="active_energy",
        field="qty",
        agg="SUM",
        period_start=date(2026, 7, 1),
        period_end=date(2026, 7, 3),
        n=3,
    )

    assert result == [10.0, None, 30.1234]
    assert len(client.calls) == 3
    assert [call["query_parameters"]["start"] for call in client.calls] == [
        "2026-07-01T00:00:00Z",
        "2026-07-02T00:00:00Z",
        "2026-07-03T00:00:00Z",
    ]
    assert [call["query_parameters"]["end"] for call in client.calls] == [
        "2026-07-01T23:59:59Z",
        "2026-07-02T23:59:59Z",
        "2026-07-03T23:59:59Z",
    ]


def test_query_returns_empty_when_measurement_does_not_exist() -> None:
    client = FailingClient(
        Exception(
            "Error during planning: table 'public.iox.weight_body_mass' not found"
        )
    )

    with capture_missing_measurements() as missing:
        assert query(client, 'SELECT * FROM "weight_body_mass"') == []

    assert missing == {"weight_body_mass"}


def test_query_preserves_real_database_failures() -> None:
    client = FailingClient(Exception("connection refused"))

    with pytest.raises(Exception, match="connection refused"):
        query(client, 'SELECT * FROM "weight_body_mass"')
