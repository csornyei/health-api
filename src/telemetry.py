import tomllib
from pathlib import Path
from typing import Sequence

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import \
    OTLPSpanExporter
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import (BatchSpanProcessor, SpanExporter,
                                            SpanExportResult)

from src.settings import Settings


def _read_version() -> str:
    pyproject = Path(__file__).parent.parent / "pyproject.toml"
    with pyproject.open("rb") as f:
        return tomllib.load(f)["project"]["version"]


class _FilterHeadSpanExporter(SpanExporter):
    def __init__(self, exporter: SpanExporter) -> None:
        self._exporter = exporter

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        filtered = [s for s in spans if "HEAD" not in s.name]
        if not filtered:
            return SpanExportResult.SUCCESS
        return self._exporter.export(filtered)

    def shutdown(self) -> None:
        self._exporter.shutdown()

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return self._exporter.force_flush(timeout_millis)


def setup_tracing(service_name: str, settings: Settings) -> None:
    resource = Resource.create(
        {
            "service.name": service_name,
            "service.version": _read_version(),
            "deployment.environment.name": settings.environment,
        }
    )

    provider = TracerProvider(resource=resource)
    provider.add_span_processor(
        BatchSpanProcessor(
            _FilterHeadSpanExporter(
                OTLPSpanExporter(
                    endpoint=settings.otel_exporter_otlp_endpoint, insecure=True
                )
            )
        )
    )
    trace.set_tracer_provider(provider)

    HTTPXClientInstrumentor().instrument()
