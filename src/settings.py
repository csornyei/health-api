from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    influxdb_host: str
    influxdb_token: str
    influxdb_database: str
    log_level: str = "INFO"
    json_logs: bool = True
    summary_query_chunk_days: int = 1

    # OpenTelemetry
    otel_exporter_otlp_endpoint: str
    environment: str = "homelab"


@lru_cache
def get_settings() -> Settings:
    return Settings()
