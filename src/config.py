from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "local"
    log_level: str = "INFO"
    app_debug: bool = False
    enable_local_auth_bypass: bool = True
    enable_startup_gap_remediation: bool = False
    startup_gap_remediation_exchange_code: str = "binance"
    startup_gap_remediation_symbols: str = "BTCUSDT_PERP"
    startup_gap_remediation_lookback_hours: int = 24
    startup_gap_remediation_raw_event_channel: str | None = None
    local_auth_user_id: str = "local-dev"
    local_auth_user_name: str = "Local Developer"
    local_auth_role: str = "admin"
    database_url: str | None = None
    redis_url: str | None = None

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "crypto_trading"
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"

    redis_host: str = "localhost"
    redis_port: int = 6379

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url

        user = quote_plus(self.postgres_user)
        password = quote_plus(self.postgres_password)
        return (
            f"postgresql+psycopg://{user}:{password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def resolved_redis_url(self) -> str:
        if self.redis_url:
            return self.redis_url

        return f"redis://{self.redis_host}:{self.redis_port}/0"


settings = Settings()
